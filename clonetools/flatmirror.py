# Copyright (c) 2010 Jan Kaliszewski (zuo). All rights reserved.
# Licensed under the MIT License.
# Python 2.4+ & 3.x -compatibile.
# This is a part of clonetools that can be used also as a standalone module.

"""
flatmirror() function makes a "flat mirror" of a given class, i.e. a fake
subclass -- reducing class hierarchy. It has significant limitations
(see: the function documentation string).
"""

from sys import version_info
try:
    from abc import ABCMeta
except ImportError:
    class ABCMeta(type): "A mockup"
try:
    from functools import partial
except ImportError:
    def partial(func, **kwargs):  # simplified equivalent
        return (lambda *args: func(*args, **kwargs))

__all__ = ('flatmirror',)


# Some builtins:

if version_info[0] >= 3:
    basestring = str
_dictproxy_type = type(object.__dict__)
if _dictproxy_type is dict:
    class _dictproxy_type(object): pass
try: next = next
except NameError:
    def next(i):
        return i.next()


# Public function:

def flatmirror(cls=None, add=None, exclude=('__dict__', '__weakref__'),
               bases=(object,), dict_factory=None, metacls=None,
               metacls_kwargs=None, register='abc'):
    """Create a new "flat mirror" (fake subclass) of a class.

    The newly created class obtains methods/attributes of the given class
    ("mixin-class") and its super classes (direct + indirect base classes).
    But the real super class hierarchy of the new class is flattened --
    i.e. limited to the classes mentioned in the bases argument.

    It doesn't work well with classes containing methods using super() or
    getting unbound methods from the classes themselves or superclasses
    (the latter issue doesn't apply to Python 3.x). In such cases try
    using clonetools.clonecls() instead.

    Arguments:
    * cls
      -- the direct base class (the "mixin class") [if omitted, rest of
      arguments will be used to create ready-to-call class decorator];
    * add [default: {}]
      -- a dictionary of attributes to be added to the created class;
      the __slots__ attribute is treated specially -- names it contain
      are added to names found in __slots__ of the "mixin class" and its
      super classes;
    * exclude [default: ('__dict__', '__weakref__')]
      -- a sequence of names of attributes that should not be mirrored;
    * bases [default: (object,)]
      -- a tuple of types to be used as base classes for the created class;
    * dict_factory [default: type(cls.__dict__); but dict if it was dictproxy]
      -- a factory (type/function) to make __dict__ for the created class;
    * metacls [default: type(cls)]
      -- a factory (metaclass) to be used to create the class;
    * metacls_kwargs [default: {}]
      -- keyword arguments for that metaclass;
    * register [default: 'abc']
      -- a callable to be called with the newly created class as the argument,
         or 'abc' -- call cls.register only if isinstance(cls, abc.ABCMeta),
         or True -- call cls.register (unconditionally),
         or False -- do not call anything (unconditionally).

    See clonetools/test.py for some usage examples.
    """
    if cls is None:
        return partial(flatmirror, add=add, exclude=exclude, bases=bases,
                       dict_factory=dict_factory, metacls=metacls,
                       metacls_kwargs=metacls_kwargs, register=register)
    name = getattr(cls, '__name__', '') + '_flatmirror'
    (dict_factory, metacls, metacls_kwargs
    ) = _get_meta_params(cls, dict_factory, metacls, metacls_kwargs)
    attrdict = _get_flatmirror_attrdict(cls, add, exclude, bases, dict_factory)
    return _get_registered_cls(metacls(name, bases, attrdict,
                                       **metacls_kwargs),
                               cls, register)


# Non-public functions:

def _get_flatmirror_attrdict(cls, add, exclude, bases, dict_factory):
    attrdict = dict_factory()
    slotset = set()
    rev_mro = reversed(cls.mro())
    supercls = next(rev_mro)
    for basecls in reversed(bases):
        # skip some redundant base classes (typically: object)
        if issubclass(basecls, supercls):
            supercls = next(rev_mro)
        else:
            break
    while True:
        slots = getattr(supercls, '__slots__', ())
        excl = frozenset(slots).union(exclude)
        slotset.update(slots)
        for attrname, obj in supercls.__dict__.items():
            if attrname not in excl:
                attrdict[attrname] = obj
        if supercls is not cls:
            supercls = next(rev_mro)
        else:
            break
    if add is not None:
        attrdict.update(add)
    slots = attrdict.get('__slots__', None)
    if slots is not None:
        if isinstance(slots, basestring):
            slots = (slots,)
        slotset.update(slots)
        attrdict['__slots__'] = tuple(slotset)
    return attrdict

def _get_meta_params(cls, dict_factory, metacls, metacls_kwargs):
    name = getattr(cls, '__name__', '') + '_flatmirror'
    if dict_factory is None:
        dict_factory = type(cls.__dict__)
        if issubclass(dict_factory, _dictproxy_type):
            dict_factory = dict
    if metacls is None:
        metacls = type(cls)
    if metacls_kwargs is None:
        metacls_kwargs = {}
    return dict_factory, metacls, metacls_kwargs

def _get_registered_cls(newcls, mixincls, register):
    if register == 'abc':
        if isinstance(mixincls, ABCMeta):
            register = mixincls.register
        else:
            register = None
    elif register and isinstance(register, bool):
        register = mixincls.register
    if register:
        register(newcls)
    return newcls
