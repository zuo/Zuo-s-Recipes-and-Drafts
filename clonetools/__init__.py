# Copyright (c) 2010 Jan Kaliszewski (zuo). All rights reserved.
# Licensed under the MIT License.
# Python 2.4+ & 3.x -compatibile.

"""
Tools for cloning classes and functions.

CAUTION: TREAT IT AS AN ALPHA VERSION! Any feedback is welcome.

Useful (hopefully...) when you need to "copy" a class or a function
to adjust it (e.g. adding __slots__ to all base clases), without hurting
the original class/function objects.

Public functions:
* clonefunc -- clone a function (user-defined, not C-builtin);
* clonecls -- clone a class (typically with its bases, except builtins);
* clone -- clone a function or a class (it's a convenience function);
* flatmirror -- create a "flat mirror" (fake subclass) of a class.

These functions (especially class cloning) are not 100% reliable
(partly, by the nature of the task).

Known bug: function closures and default argument values are not copied
and adjusted when cloning class methods (could be fixed in the future)
-- it causes problems, e.g. with classes defined somewhere else than
within global (module) scope.

Auxiliary container classes:
* IdentContainer -- with identity-based presence test ('in'-test).
* ContainsAll -- instances always return True for presence test.
"""

from inspect import isfunction
from sys import version_info
from types import FunctionType

from flatmirror import (flatmirror, ABCMeta, next, partial,
                        _get_meta_params, _get_registered_cls)

__all__ = ('clonecls', 'clonefunc', 'clone', 'flatmirror',
           'ContainsAll', 'IdentContainer')


# Constants and builtins:

if version_info[0] >= 3:
    import builtins
    FUNC_ATTR_MAP = {
        '__globals__': '__globals__',
        '__closure__': '__closure__',
        '__code__': '__code__',
    }
    basestring = str
else:
    import __builtin__ as builtins
    FUNC_ATTR_MAP = {
        '__globals__': 'func_globals',
        '__closure__': 'func_closure',
        '__defaults__': 'func_defaults',
        '__code__': 'func_code',
        '__dict__': 'func_dict',
    }
BUILTIN_OBJS = vars(builtins).values()
SOME_FUNC_ATTRS = [FUNC_ATTR_MAP.get(a, a)
                   for a in ('__defaults__', '__doc__', '__module__')]
SOME_FUNC_DICTS = [FUNC_ATTR_MAP.get(a, a)
                   for a in ('__dict__', '__annotations__', '__kwdefaults__')]


# Auxiliary types:

class IdentContainer(object):
    """Simple container with identity-based 'in'-test."""
    def __init__(self, actual_container):
        """Initialize with an actual container."""
        self.actual_container = actual_container
    def __contains__(self, key):
        for obj in self.actual_container:
            if obj is key:
                return True
        return False

class ContainsAll(object):
    """Dummy container -- always returning True for 'in'-test."""
    def __contains__(self, key):
        return True


# Public functions:

def clonefunc(func, to_update=None):  # side effect on the to_update list!
    """Clone a given function (for user-defined only, i.e. not builtins etc.).

    Arguments:
    * func
      -- the function to be cloned;
    * to_update [default: None]
      -- if a list or True given, all function dicts (globals, function
         __dict__, kw-defaults, annotations) will be copied using their
         copy() methods; additionaly, for a list, all copied dictionaries
         will be appended to that list.

    See clonetools/test.py for some usage examples.
    """
    func_globals = getattr(func, FUNC_ATTR_MAP['__globals__'])
    lets_append = isinstance(to_update, list)
    if lets_append or to_update:
        func_globals = func_globals.copy()
        if lets_append:
            to_update.append(func_globals)
    newfunc = FunctionType(getattr(func, FUNC_ATTR_MAP['__code__']),
                           func_globals,
                           closure=getattr(func, FUNC_ATTR_MAP['__closure__']))
    for attr in SOME_FUNC_ATTRS:
        setattr(newfunc, attr, getattr(func, attr))
    for attr in SOME_FUNC_DICTS:
        a_dict = getattr(func, attr, None)
        if a_dict is not None:
            if lets_append or to_update:
                a_dict = a_dict.copy()
                if lets_append:
                    to_update.append(a_dict)
            setattr(newfunc, attr, a_dict)
    return newfunc


def clonecls(cls, slots=None, exclude=('__dict__', '__weakref__'),
             to_clone=None, dict_factory=None, metacls=None,
             metacls_kwargs=None, register='abc', ignore_base_err=False):
    """Clone a given class (typically cloning also its bases, except builtins).

    Arguments:
    * cls
      -- the class to be cloned;
    * slots [default: None]
      -- if not None, __slots__ attribute is added to the cloned class
      and its cloned super classes; the actual argument content is added
      to the highest possible class in the hierarchy, rest are left empty;
      all __slots__ names found in classes are preserved;
    * exclude [default: ('__dict__', '__weakref__')]
      -- a sequence of names of attributes that should not be mirrored/cloned;
    * to_clone [default: all super classes of cls]
      -- a container of super classes that should be cloned, apart from cls;
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
         or False -- do not call anything (unconditionally);
    * ignore_base_err [default: False]
      -- if true, ignore Atribute|TypeErrors occuring when a base class
      is being cloned: instead of raising exceptions, return original
      class objects.
    """
    to_update = []
    old2new_classes = {}
    if slots is not None:
        if isinstance(slots, basestring):
            slots = (slots,)
        slots = list(slots)
    if to_clone is not None:
        to_clone = IdentContainer((cls,) + tuple(to_clone))
    else:
        to_clone = ContainsAll()
    new_cls = _clone_cls(cls, slots, to_update, old2new_classes,
                         exclude, to_clone, dict_factory,
                         metacls, metacls_kwargs, ignore_base_err)
    if new_cls is cls:
        raise TypeError('%r cannot be cloned' % cls)
    for a_dict in to_update:
        for k, obj in a_dict.items():
            for old, new in old2new_classes.items():
                if obj is old:
                    a_dict[k] = new
                    break
    return _get_registered_cls(new_cls, cls, register)


def clone(*args, **kwargs):
    """Call clonefunc()/clonecls() (depending on first argument type)."""
    if isfunction(args[0]):
        return clonefunc(*args, **kwargs)
    else:
        return clonecls(*args, **kwargs)


# Non-public functions:

def _get_newslots_and_excl(cls, slots, exclude):
    cls_slots = getattr(cls, '__slots__', None)
    if cls_slots is not None:
        if isinstance(cls_slots, basestring):
            cls_slots = (cls_slots,)
        excl = set(exclude).union(cls_slots)
        new_slots = list(cls_slots)
        if slots is not None:
            new_slots.extend(slots)
    else:
        excl = set(exclude)
        if slots is not None:
            new_slots = list(slots)
        else:
            new_slots = None
    excl.add('__slots__')
    return new_slots, excl

def _clone_cls(cls,                                # side effect on these
               slots, to_update, old2new_classes,  # <- mutable arguments!
               exclude, to_clone, dict_factory,
               metacls, metacls_kwargs, ignore_base_err,
               _builtin_objs=IdentContainer(BUILTIN_OBJS)):
    if cls not in to_clone or cls in _builtin_objs:
        return cls
    try:
        (bases   # recursion:
        ) = tuple(_clone_cls(basecls, slots, to_update, old2new_classes,
                             exclude, to_clone, dict_factory,
                             metacls, metacls_kwargs, ignore_base_err)
                  for basecls in cls.__bases__)
        old2new_classes.update((old, new)
                               for old, new in zip(cls.__bases__, bases)
                               if old is not new)
        (dict_factory, metacls, metacls_kwargs
        ) = _get_meta_params(cls, dict_factory, metacls, metacls_kwargs)
        attrdict = dict_factory()
        new_slots, to_exclude = _get_newslots_and_excl(cls, slots, exclude)
        if new_slots is not None:
            attrdict['__slots__'] = new_slots
        for attrname, obj in cls.__dict__.items():
            if attrname not in to_exclude:
                if isfunction(obj):
                    obj = clonefunc(obj, to_update)
                attrdict[attrname] = obj
        name = getattr(cls, '__name__', '') + '_clone'
        new_cls = metacls(name, bases, attrdict, **metacls_kwargs)
    except (TypeError, AttributeError):
        if ignore_base_err:
            return cls
        raise
    else:
        if slots is not None:
            del slots[:]
        return new_cls
