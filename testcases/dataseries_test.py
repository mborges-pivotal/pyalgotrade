# PyAlgoTrade
# 
# Copyright 2011 Gabriel Martin Becedillas Ruiz
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

import unittest
import datetime

from pyalgotrade import dataseries
from pyalgotrade import bar

class TestSequenceDataSeries(unittest.TestCase):
	def testEmpty(self):
		ds = dataseries.SequenceDataSeries([])
		self.assertTrue(ds.getFirstValidPos() == 0)
		self.assertTrue(ds.getLength() == 0)
		with self.assertRaises(IndexError):
			ds[-1]
		with self.assertRaises(IndexError):
			ds[-2]
		with self.assertRaises(IndexError):
			ds[0]
		with self.assertRaises(IndexError):
			ds[1]

	def testNonEmpty(self):
		ds = dataseries.SequenceDataSeries(range(10))
		self.assertTrue(ds.getFirstValidPos() == 0)
		self.assertTrue(ds.getLength() == 10)
		self.assertTrue(ds[-1] == 9)
		self.assertTrue(ds[-2] == 8)
		self.assertTrue(ds[0] == 0)
		self.assertTrue(ds[1] == 1)

		self.assertTrue(ds.getValues(1) == [9])
		self.assertTrue(ds.getValues(2) == [8, 9])
		self.assertTrue(ds.getValues(1, 1) == [8])
		self.assertTrue(ds.getValues(2, 1) == [7, 8])

		self.assertTrue(ds.getValuesAbsolute(1, 3) == [1, 2, 3])
		self.assertTrue(ds.getValuesAbsolute(9, 9) == [9])
		self.assertTrue(ds.getValuesAbsolute(9, 10) == None)
		self.assertTrue(ds.getValuesAbsolute(9, 10, True) == [9, None])

	def testSeqLikeOps(self):
		seq = range(10)
		ds = dataseries.SequenceDataSeries(seq)

		# Test length and every item.
		self.assertEqual(len(ds), len(seq))
		for i in xrange(len(seq)):
			self.assertEqual(ds[i], seq[i])

		# Test negative indices
		self.assertEqual(ds[-1], seq[-1])
		self.assertEqual(ds[-2], seq[-2])
		self.assertEqual(ds[-9], seq[-9])

		# Test slices
		sl = slice(0,1,2)
		self.assertEqual(ds[sl], seq[sl])
		sl = slice(0,9,2)
		self.assertEqual(ds[sl], seq[sl])
		sl = slice(0,-1,1)
		self.assertEqual(ds[sl], seq[sl])

		for i in xrange(-100, 100):
			self.assertEqual(ds[i:], seq[i:])

		for step in xrange(1, 10):
			for i in xrange(-100, 100):
				self.assertEqual(ds[i::step], seq[i::step])

class TestBarDataSeries(unittest.TestCase):
	def testEmpty(self):
		ds = dataseries.BarDataSeries()
		self.assertTrue(ds.getValue(-2) == None)
		self.assertTrue(ds.getValue(-1) == None)
		self.assertTrue(ds.getValue() == None)
		self.assertTrue(ds.getValue(1) == None)
		self.assertTrue(ds.getValue(2) == None)

		with self.assertRaises(IndexError):
			ds[-1]
		with self.assertRaises(IndexError):
			ds[0]
		with self.assertRaises(IndexError):
			ds[1000]

	def testAppendInvalidDatetime(self):
		ds = dataseries.BarDataSeries()
		for i in range(10):
			now = datetime.datetime.now() + datetime.timedelta(seconds=i)
			ds.appendValue( bar.Bar(now, 0, 0, 0, 0, 0, 0) )
			# Adding the same datetime twice should fail
			self.assertRaises(Exception, ds.appendValue, bar.Bar(now, 0, 0, 0, 0, 0, 0))
			# Adding a previous datetime should fail
			self.assertRaises(Exception, ds.appendValue, bar.Bar(now - datetime.timedelta(seconds=i), 0, 0, 0, 0, 0, 0))

	def testNonEmpty(self):
		ds = dataseries.BarDataSeries()
		for i in range(10):
			ds.appendValue( bar.Bar(datetime.datetime.now() + datetime.timedelta(seconds=i), 0, 0, 0, 0, 0, 0) )

		for i in range(0, 10):
			self.assertTrue(ds.getValue(i) != None)

	def __testGetValue(self, ds, itemCount, value):
		for i in range(0, itemCount):
			self.assertTrue(ds.getValue(i) == value)

	def testNestedDataSeries(self):
		ds = dataseries.BarDataSeries()
		for i in range(10):
			ds.appendValue( bar.Bar(datetime.datetime.now() + datetime.timedelta(seconds=i), 2, 4, 1, 3, 10, 3) )

		self.__testGetValue(ds.getOpenDataSeries(), 10, 2)
		self.__testGetValue(ds.getCloseDataSeries(), 10, 3)
		self.__testGetValue(ds.getHighDataSeries(), 10, 4)
		self.__testGetValue(ds.getLowDataSeries(), 10, 1)
		self.__testGetValue(ds.getVolumeDataSeries(), 10, 10)
		self.__testGetValue(ds.getAdjCloseDataSeries(), 10, 3)

	def testSeqLikeOps(self):
		ds = dataseries.BarDataSeries()
		for i in range(10):
			ds.appendValue( bar.Bar(datetime.datetime.now() + datetime.timedelta(seconds=i), 2, 4, 1, 3, 10, 3) )

		self.assertEqual(ds[-1], ds.getValue())
		self.assertEqual(ds[-2], ds.getValue(1))
		self.assertEqual(ds[0], ds[0])
		self.assertEqual(ds[1], ds[1])
		self.assertEqual(ds[-2:][-1], ds.getValue())

def getTestCases():
	ret = []

	ret.append(TestSequenceDataSeries("testEmpty"))
	ret.append(TestSequenceDataSeries("testNonEmpty"))
	ret.append(TestSequenceDataSeries("testSeqLikeOps"))

	ret.append(TestBarDataSeries("testEmpty"))
	ret.append(TestBarDataSeries("testAppendInvalidDatetime"))
	ret.append(TestBarDataSeries("testNonEmpty"))
	ret.append(TestBarDataSeries("testNestedDataSeries"))
	ret.append(TestBarDataSeries("testSeqLikeOps"))
	return ret

