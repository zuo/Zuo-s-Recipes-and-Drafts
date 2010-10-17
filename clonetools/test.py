# Copyright (c) 2010 Jan Kaliszewski (zuo). All rights reserved.
# Licensed under the MIT License.
# Python 2.4+ & 3.x -compatibile.

"""Quick test."""

import unittest
from __init__ import *


class SimpleTest(unittest.TestCase):

    def setUp(self):
        global A, B, C, D, E, F
        A = B = C = D = E = F = None

    def tearDown(self):
        global A, B, C, D, E, F
        del A, B, C, D, E, F

    def _test_and_get_instance(self):
        self.assertFalse(isinstance(F, E))
        self.assertFalse(isinstance(F, A))
        self.assertTrue(hasattr(F, 'a_slot'))
        self.assertTrue(hasattr(F, 'a_slot2'))
        obj = F()
        self.assertFalse(hasattr(obj, 'a_slot'))
        self.assertFalse(hasattr(obj, 'a_slot2'))
        for name in 'abcdef':
            # testing methods
            method = getattr(obj, name, obj.x)
            self.assertTrue(method(), name)
        A().x = 3
        # attribute not included in __slots__ => AttributeError
        self.assertRaises(AttributeError, setattr, obj, 'aaa', 3)
        return obj

    @staticmethod
    def _make_method(s):
        return lambda self: s

    def _test_flatmirror_and_get_instance(self, base_class):
        global A, B, C, D, E, F
        class A(base_class): a = self._make_method('a')
        class B(A): b = self._make_method('b')
        class C(B):
            __slots__ = 'a_slot'
            c = self._make_method('c')
        class D(A): d = self._make_method('d')
        class E(C, D): e = self._make_method('e')
        F = flatmirror(E, add={'__slots__': 'a_slot2'},
                       bases=(base_class,))
        F.f = self._make_method('f')
        F.x = self._make_method('x')
        return self._test_and_get_instance()

    def _test_clone_and_get_instance(self, base_class):
        # only global classes can be cloned
        global A, B, C, D, E, F
        class A(base_class): a = self._make_method('a')
        class B(A): b = self._make_method('b')
        class C(B):
            __slots__ = 'a_slot'
            def c(self):
                super(C, self).a()
                return 'c'
        class D(A):
            def d(self):
                super(D, self).a()
                return 'd'
        class E(C, D):
            def e(self):
                C.c(self)
                D.d(self)
                return 'e'
        F = clone(E, slots='a_slot2')
        F.f = self._make_method('f')
        F.x = self._make_method('x')
        return self._test_and_get_instance()

    def _test_dict(self, obj):
        obj['aaa'] = 3
        self.assertEqual(obj['aaa'], 3)
        self.assertRaises(KeyError, obj.__getitem__, 'zzz')

    def test_object_subclass_flatmirror(self):
        self._test_flatmirror_and_get_instance(object)

    def test_dict_subclass_flatmirror(self):
        self._test_dict(self._test_flatmirror_and_get_instance(dict))

    def test_object_subclass_clone(self):
        self._test_flatmirror_and_get_instance(object)

    def test_dict_subclass_clone(self):
        self._test_dict(self._test_clone_and_get_instance(dict))

try:
    from collections import Iterable, Mapping, MutableMapping
except ImportError:
    pass
else:
    class TestWithMutableMappingABC(unittest.TestCase):

        def _get_class(self, base_class):
            class MyDict(base_class):
                __slots__ = ('_keys', '_value')
                def __init__(self, value=0):
                    self._keys = set()
                    self._value = value
                def __getitem__(self, key):
                    if key in self._keys:
                        return self._value
                    raise KeyError(key)
                def __setitem__(self, key, value):
                    self._keys.add(key)
                    self._value = value
                def __delitem__(self, key):
                    self._keys.remove(key)
                def __len__(self):
                    return len(self._keys)
                def __contains__(self, key):
                    return key in self._keys
                def __iter__(self):
                    return iter(self._keys)
                an_attr = 345
            return MyDict

        def _test_registered(self, d, MyDict):
            self.assertTrue(issubclass(MyDict, MutableMapping))
            self.assertTrue(issubclass(MyDict, Mapping))
            self.assertTrue(issubclass(MyDict, Iterable))
            self.assertTrue(isinstance(d, MutableMapping))
            self.assertTrue(isinstance(d, Mapping))
            self.assertTrue(isinstance(d, Iterable))

        def _test_not_registered(self, d, MyDict):
            self.assertFalse(issubclass(MyDict, MutableMapping))
            self.assertFalse(issubclass(MyDict, Mapping))
            self.assertTrue(issubclass(MyDict, Iterable))  # (has __iter__)
            self.assertFalse(isinstance(d, MutableMapping))
            self.assertFalse(isinstance(d, Mapping))
            self.assertTrue(isinstance(d, Iterable))  # (has __iter__)

        def _test_cls_and_instance(self, MyDict, was_registered):
            self.assertEqual(getattr(MyDict, 'an_attr', None), 345)
            self.assertTrue(hasattr(MyDict, '_keys'))
            self.assertTrue(hasattr(MyDict, '_value'))
            d = MyDict(1)
            self.assertEqual(getattr(d, 'an_attr', None), 345)
            self.assertTrue(isinstance(d, MyDict))
            if was_registered:
                self._test_registered(d, MyDict)
            else:
                self._test_not_registered(d, MyDict)
            # testing some mapping methods
            d['x'] = 5
            d['y'] = 10
            self.assertTrue(d)
            self.assertEqual(d.pop('x'), 10)
            self.assertEqual(d.popitem(), ('y', 10))
            self.assertFalse(d)
            # attribute not included in __slots__ => AttributeError
            self.assertRaises(AttributeError, setattr, d, 'zzz', 3)

        def test_mirror_then_subclass(self):
            reg = 'abc'  # register as ABC subclass
            mirrored = flatmirror(MutableMapping, add=dict(__slots__=()),
                                  register=reg)
            self._test_cls_and_instance(self._get_class(mirrored), reg)
            reg = None   # do not register
            mirrored = flatmirror(MutableMapping, add=dict(__slots__=()),
                                  register=reg)
            self._test_cls_and_instance(self._get_class(mirrored), reg)

        def test_subclass_then_mirror(self):
            reg = 'abc'
            not_mirrored = self._get_class(MutableMapping)
            self._test_cls_and_instance(flatmirror(not_mirrored,
                                        register=reg), reg)
            reg = None
            not_mirrored = self._get_class(MutableMapping)
            self._test_cls_and_instance(flatmirror(not_mirrored,
                                        register=reg), reg)

        def test_abstract_mirror(self):
            class MyDict(MutableMapping): pass
            # trying to instantiate abstract class => TypeError
            self.assertRaises(TypeError, flatmirror(MyDict), 1)
            self.assertRaises(TypeError, flatmirror()(MyDict), 1)

        def test_clone_then_subclass(self):
            reg = 'abc'
            cls_clone = clonecls(MutableMapping, slots=(), register=reg)
            self._test_cls_and_instance(self._get_class(cls_clone), reg)
            reg = None
            cls_clone = clonecls(MutableMapping, slots=(), register=reg)
            self._test_cls_and_instance(self._get_class(cls_clone), reg)

        def test_subclass_then_clone(self):
            reg = 'abc'
            cls_clone = clonecls(MutableMapping, slots=(), register=reg)
            self._test_cls_and_instance(self._get_class(cls_clone), reg)
            reg = None
            cls = self._get_class(MutableMapping)
            self._test_cls_and_instance(clonecls(cls, slots=(),
                                                   register=reg), reg)

        def test_abstract_clone(self):
            class MyDict(MutableMapping): pass
            # trying to instantiate an abstract class => TypeError
            self.assertRaises(TypeError, clonecls(MyDict), 1)


if __name__ == '__main__':
    unittest.main()
