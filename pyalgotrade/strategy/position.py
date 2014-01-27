# PyAlgoTrade
#
# Copyright 2011-2013 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
.. moduleauthor:: Gabriel Martin Becedillas Ruiz <gabriel.becedillas@gmail.com>
"""

from pyalgotrade.stratanalyzer import returns
from pyalgotrade import warninghelpers
import pyalgotrade.broker


class Position(object):
    """Base class for positions.

    :param strategy: The strategy that this position belongs to.
    :type strategy: :class:`pyalgotrade.strategy.BaseStrategy`.
    :param entryOrder: The order used to enter the position.
    :type entryOrder: :class:`pyalgotrade.broker.Order`
    :param goodTillCanceled: True if the entry order should be set as good till canceled.
    :type goodTillCanceled: boolean.

    .. note::
        This is a base class and should not be used directly.
    """

    def __init__(self, strategy, entryOrder, goodTillCanceled):
        # The order must be created but not submitted.
        assert(entryOrder.isInitial())

        self.__activeOrders = {entryOrder.getId(): entryOrder}
        self.__shares = 0
        self.__strategy = strategy
        self.__entryOrder = entryOrder
        self.__exitOrder = None
        self.__exitOnSessionClose = False

        entryOrder.setGoodTillCanceled(goodTillCanceled)
        # This may raise an exception, so we wan't to place the order before moving forward and registering the order in the strategy.
        strategy.getBroker().placeOrder(entryOrder)

        self.getStrategy().registerPositionOrder(self, entryOrder)

    def getStrategy(self):
        return self.__strategy

    def getLastPrice(self):
        return self.__strategy.getLastPrice(self.getInstrument())

    def getActiveOrders(self):
        """Returns a list with the active orders."""
        return self.__activeOrders.values()

    def getShares(self):
        """Returns the number of shares.
        This will be a possitive number for a long position,
        and a negative number for a short position.

        .. note::
            If the entry order was not filled, or if the position is closed, then the number of shares will be 0.
        """
        return self.__shares

    def entryActive(self):
        """Returns True if the entry order is active."""
        return self.__entryOrder is not None and self.__entryOrder.isActive()

    def entryFilled(self):
        """Returns True if the entry order was filled."""
        return self.__entryOrder is not None and self.__entryOrder.isFilled()

    def exitActive(self):
        """Returns True if the exit order is active."""
        return self.__exitOrder is not None and self.__exitOrder.isActive()

    def exitFilled(self):
        """Returns True if the exit order was filled."""
        return self.__exitOrder is not None and self.__exitOrder.isFilled()

    def getGoodTillCanceled(self):
        return self.__entryOrder.getGoodTillCanceled()

    def setExitOnSessionClose(self, exitOnSessionClose):
        # Deprecated since v0.15
        warninghelpers.deprecation_warning("Auto exit on session close will be deprecated in the next version.", stacklevel=2)
        self.__exitOnSessionClose = exitOnSessionClose

    def getExitOnSessionClose(self):
        return self.__exitOnSessionClose

    def getEntryOrder(self):
        """Returns the :class:`pyalgotrade.broker.Order` used to enter the position."""
        return self.__entryOrder

    def setExitOrder(self, exitOrder):
        assert(self.__exitOrder is None or not self.__exitOrder.isActive())
        assert(exitOrder.isSubmitted())
        self.__activeOrders[exitOrder.getId()] = exitOrder
        self.__exitOrder = exitOrder
        self.getStrategy().registerPositionOrder(self, exitOrder)

    def getExitOrder(self):
        """Returns the :class:`pyalgotrade.broker.Order` used to exit the position. If this position hasn't been closed yet, None is returned."""
        return self.__exitOrder

    def getInstrument(self):
        """Returns the instrument used for this position."""
        return self.__entryOrder.getInstrument()

    def getQuantity(self):
        # TODO: Deprecate this and use abs(getShares()) instead.
        return self.__entryOrder.getQuantity()

    def cancelEntry(self):
        """Cancels the entry order if its active."""
        if self.getEntryOrder().isActive():
            self.getStrategy().getBroker().cancelOrder(self.getEntryOrder())

    def cancelExit(self):
        """Cancels the exit order if its active."""
        if self.getExitOrder() is not None and self.getExitOrder().isActive():
            self.getStrategy().getBroker().cancelOrder(self.getExitOrder())

    def exit(self, limitPrice=None, stopPrice=None, goodTillCanceled=None):
        """Generates the exit order for the position.

        :param limitPrice: The limit price.
        :type limitPrice: float.
        :param stopPrice: The stop price.
        :type stopPrice: float.
        :param goodTillCanceled: True if the exit order is good till canceled. If False then the order gets automatically canceled when the session closes. If None, then it will match the entry order.
        :type goodTillCanceled: boolean.

        .. note::
            * If the entry order was not filled yet, it will be canceled.
            * If the exit order for this position was filled, this won't have any effect.
            * If the exit order for this position is pending, an exception will be raised. The exit order should be canceled first.
            * If limitPrice is not set and stopPrice is not set, then a :class:`pyalgotrade.broker.MarketOrder` is used to exit the position.
            * If limitPrice is set and stopPrice is not set, then a :class:`pyalgotrade.broker.LimitOrder` is used to exit the position.
            * If limitPrice is not set and stopPrice is set, then a :class:`pyalgotrade.broker.StopOrder` is used to exit the position.
            * If limitPrice is set and stopPrice is set, then a :class:`pyalgotrade.broker.StopLimitOrder` is used to exit the position.
        """

        if self.getEntryOrder().isActive():
            assert(self.__shares == 0)
            self.getStrategy().getBroker().cancelOrder(self.getEntryOrder())
            return

        if self.exitFilled():
            assert(self.__shares == 0)
            return

        # Fail if a previous exit order is active.
        if self.getExitOrder() is not None and self.getExitOrder().isActive():
            raise Exception("Exit order is active and it should be canceled first")

        closeOrder = self.buildExitOrder(limitPrice, stopPrice)

        # If goodTillCanceled was not set, match the entry order.
        if goodTillCanceled is None:
            goodTillCanceled = self.__entryOrder.getGoodTillCanceled()
        closeOrder.setGoodTillCanceled(goodTillCanceled)

        self.getStrategy().getBroker().placeOrder(closeOrder)
        self.setExitOrder(closeOrder)

    def checkExitOnSessionClose(self, bars):
        ret = None
        # If the position was set to exit on session close, and this is the penultimate bar then:
        # * Create the exit order if the entry was filled.
        # * Cancel the entry order if it was not filled so far.
        if self.__exitOnSessionClose and self.__exitOrder is None:
            bar = bars.getBar(self.getInstrument())
            if bar and bar.getBarsTillSessionClose() == 1:
                if self.entryFilled():
                    ret = self.buildExitOnSessionCloseOrder()
                    self.getStrategy().getBroker().placeOrder(ret)
                    self.setExitOrder(ret)
                    self.getStrategy().registerPositionOrder(self, ret)
                else:
                    self.getStrategy().getBroker().cancelOrder(self.getEntryOrder())
        return ret

    def onOrderUpdated(self, broker, order):
        if not order.isActive():
            del self.__activeOrders[order.getId()]

        # Update the number of shares.
        if order.isFilled() or order.isPartiallyFilled():
            if order.isBuy():
                self.__shares += order.getExecutionInfo().getQuantity()
            else:
                self.__shares -= order.getExecutionInfo().getQuantity()

    def getUnrealizedReturn(self, price=None):
        """Calculates the unrealized returns for the position.

        :param price: Price used to calculate the returns.
            This value is used as the current price and compared against your entry price.
            If None then the last available price will be used.
        :type price: float.
        :rtype: A float between 0 and 1.

        .. note::
            The position must be open.
        """
        if not self.entryFilled():
            raise Exception("Position not opened yet")
        elif self.exitFilled():
            raise Exception("Position already closed")

        if price is None:
            price = self.getLastPrice()
        return self.getReturnImpl(price, False)

    def getReturn(self, includeCommissions=True):
        """Calculates the returns for the position.

        :param includeCommissions: True to include commisions in the calculation.
        :type includeCommissions: boolean.
        :rtype: A float between 0 and 1.

        .. note::
            The position must be closed.
        """
        if not self.entryFilled():
            raise Exception("Position not opened yet")
        elif not self.exitFilled():
            raise Exception("Position not closed yet")
        return self.getReturnImpl(self.getExitOrder().getExecutionInfo().getPrice(), includeCommissions)

    def getResult(self):
        warninghelpers.deprecation_warning("getResult will be deprecated in the next version. Please use getReturn instead.", stacklevel=2)
        return self.getReturn(False)

    def getNetProfit(self, includeCommissions=True):
        """Calculates the PnL for the position.

        :param includeCommissions: True to include commisions in the calculation.
        :type includeCommissions: boolean.
        :rtype: A float with the PnL.

        .. note::
            The position must be closed.
        """
        if not self.entryFilled():
            raise Exception("Position not opened yet")
        elif not self.exitFilled():
            raise Exception("Position not closed yet")
        return self.getNetProfitImpl(self.getExitOrder().getExecutionInfo().getPrice(), includeCommissions)

    def getUnrealizedNetProfit(self, price=None):
        """Calculates the unrealized PnL for the position.

        :param price: Price used to calculate the PnL.
            This value is used as the current price and compared against the entry price.
            If None then the last available price will be used.
        :type price: float.
        :rtype: A float with the unrealized PnL.

        .. note::
            The position must be open.
        """

        if not self.entryFilled():
            raise Exception("Position not opened yet")
        elif self.exitFilled():
            raise Exception("Position already closed")

        if price is None:
            price = self.getLastPrice()
        return self.getNetProfitImpl(price, False)

    def getReturnImpl(self, price, includeCommissions):
        raise NotImplementedError()

    def getNetProfitImpl(self, price, includeCommissions):
        raise NotImplementedError()

    def buildExitOrder(self, limitPrice, stopPrice):
        raise NotImplementedError()

    def buildExitOnSessionCloseOrder(self):
        raise NotImplementedError()

    def isLong(self):
        raise NotImplementedError()

    def isShort(self):
        return not self.isLong()

    def isOpen(self):
        """Returns True if the position is open."""
        # Entry accepted    -> open
        # Entry canceled    -> closed
        # Entry filled        -> check exit
        #     No exit order    -> open
        #     Exit accepted    -> open
        #     Exit canceled    -> open
        #     Exit filled        -> closed

        ret = False
        if self.__entryOrder.isActive():
            ret = True
        elif self.__entryOrder.isFilled():
            if self.__exitOrder is None or not self.__exitOrder.isFilled():
                ret = True
        return ret


# This class is reponsible for order management in long positions.
class LongPosition(Position):
    def __init__(self, strategy, instrument, limitPrice, stopPrice, quantity, goodTillCanceled):
        if limitPrice is None and stopPrice is None:
            entryOrder = strategy.getBroker().createMarketOrder(pyalgotrade.broker.Order.Action.BUY, instrument, quantity, False)
        elif limitPrice is not None and stopPrice is None:
            entryOrder = strategy.getBroker().createLimitOrder(pyalgotrade.broker.Order.Action.BUY, instrument, limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopOrder(pyalgotrade.broker.Order.Action.BUY, instrument, stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopLimitOrder(pyalgotrade.broker.Order.Action.BUY, instrument, stopPrice, limitPrice, quantity)
        else:
            assert(False)

        Position.__init__(self, strategy, entryOrder, goodTillCanceled)

    def __getPosTracker(self):
        ret = returns.PositionTracker()
        entryExecInfo = self.getEntryOrder().getExecutionInfo()
        ret.buy(entryExecInfo.getQuantity(), entryExecInfo.getPrice(), entryExecInfo.getCommission())
        if self.exitFilled():
            exitExecInfo = self.getExitOrder().getExecutionInfo()
            ret.sell(exitExecInfo.getQuantity(), exitExecInfo.getPrice(), exitExecInfo.getCommission())
        return ret

    def getReturnImpl(self, price, includeCommissions):
        return self.__getPosTracker().getReturn(price, includeCommissions)

    def getNetProfitImpl(self, price, includeCommissions):
        return self.__getPosTracker().getNetProfit(price, includeCommissions)

    def buildExitOrder(self, limitPrice, stopPrice):
        quantity = self.getShares()
        if limitPrice is None and stopPrice is None:
            ret = self.getStrategy().getBroker().createMarketOrder(pyalgotrade.broker.Order.Action.SELL, self.getInstrument(), quantity, False)
        elif limitPrice is not None and stopPrice is None:
            ret = self.getStrategy().getBroker().createLimitOrder(pyalgotrade.broker.Order.Action.SELL, self.getInstrument(), limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopOrder(pyalgotrade.broker.Order.Action.SELL, self.getInstrument(), stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopLimitOrder(pyalgotrade.broker.Order.Action.SELL, self.getInstrument(), stopPrice, limitPrice, quantity)
        else:
            assert(False)

        return ret

    def buildExitOnSessionCloseOrder(self):
        quantity = self.getShares()
        ret = self.getStrategy().getBroker().createMarketOrder(pyalgotrade.broker.Order.Action.SELL, self.getInstrument(), quantity, True)
        ret.setGoodTillCanceled(True)  # Mark the exit order as GTC since we want to exit ASAP and avoid this order to get canceled.
        return ret

    def isLong(self):
        return True


# This class is reponsible for order management in short positions.
class ShortPosition(Position):
    def __init__(self, strategy, instrument, limitPrice, stopPrice, quantity, goodTillCanceled):
        if limitPrice is None and stopPrice is None:
            entryOrder = strategy.getBroker().createMarketOrder(pyalgotrade.broker.Order.Action.SELL_SHORT, instrument, quantity, False)
        elif limitPrice is not None and stopPrice is None:
            entryOrder = strategy.getBroker().createLimitOrder(pyalgotrade.broker.Order.Action.SELL_SHORT, instrument, limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopOrder(pyalgotrade.broker.Order.Action.SELL_SHORT, instrument, stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            entryOrder = strategy.getBroker().createStopLimitOrder(pyalgotrade.broker.Order.Action.SELL_SHORT, instrument, stopPrice, limitPrice, quantity)
        else:
            assert(False)

        Position.__init__(self, strategy, entryOrder, goodTillCanceled)

    def __getPosTracker(self):
        ret = returns.PositionTracker()
        entryExecInfo = self.getEntryOrder().getExecutionInfo()
        ret.sell(entryExecInfo.getQuantity(), entryExecInfo.getPrice(), entryExecInfo.getCommission())
        if self.exitFilled():
            exitExecInfo = self.getExitOrder().getExecutionInfo()
            ret.buy(exitExecInfo.getQuantity(), exitExecInfo.getPrice(), exitExecInfo.getCommission())
        return ret

    def getReturnImpl(self, price, includeCommissions):
        return self.__getPosTracker().getReturn(price, includeCommissions)

    def getNetProfitImpl(self, price, includeCommissions):
        return self.__getPosTracker().getNetProfit(price, includeCommissions)

    def buildExitOrder(self, limitPrice, stopPrice):
        quantity = self.getShares() * -1
        if limitPrice is None and stopPrice is None:
            ret = self.getStrategy().getBroker().createMarketOrder(pyalgotrade.broker.Order.Action.BUY_TO_COVER, self.getInstrument(), quantity, False)
        elif limitPrice is not None and stopPrice is None:
            ret = self.getStrategy().getBroker().createLimitOrder(pyalgotrade.broker.Order.Action.BUY_TO_COVER, self.getInstrument(), limitPrice, quantity)
        elif limitPrice is None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopOrder(pyalgotrade.broker.Order.Action.BUY_TO_COVER, self.getInstrument(), stopPrice, quantity)
        elif limitPrice is not None and stopPrice is not None:
            ret = self.getStrategy().getBroker().createStopLimitOrder(pyalgotrade.broker.Order.Action.BUY_TO_COVER, self.getInstrument(), stopPrice, limitPrice, quantity)
        else:
            assert(False)

        return ret

    def buildExitOnSessionCloseOrder(self):
        quantity = self.getShares() * -1
        ret = self.getStrategy().getBroker().createMarketOrder(pyalgotrade.broker.Order.Action.BUY_TO_COVER, self.getInstrument(), quantity, True)
        ret.setGoodTillCanceled(True)  # Mark the exit order as GTC since we want to exit ASAP and avoid this order to get canceled.
        return ret

    def isLong(self):
        return False
