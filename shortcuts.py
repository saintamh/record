#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
$Id$
Herve Saint-Amand
Edinburgh
"""

#----------------------------------------------------------------------------------------------------------------------------------
# includes

# standards
import re

# saintamh
from ..util.codegen import SourceCodeTemplate

# this module
from .record import Field, compile_field_def

#----------------------------------------------------------------------------------------------------------------------------------

def value_check(name, check):
    def func(fdef):
        fdef = compile_field_def(fdef)
        if fdef.check is not None:
            raise Exception("I haven't figured out how to chain value checks yet")
        return fdef.derive(check=check)
    func.__name__ = name
    return func

nonempty = value_check('nonempty', 'len({}) > 0')

nonnegative = value_check('nonnegative', '{} >= 0')
strictly_positive = value_check('strictly_positive', '{} > 0')

#----------------------------------------------------------------------------------------------------------------------------------

def regex_check(name, char_def):
    def func(n=None):
        multiplier = ('{{%d}}' % n) if n is not None else '*'
        fdef = Field(
            type = str,
            check = "$re.search(r'^[%s]%s$',{})" % (char_def, multiplier),
        )
        return fdef
    func.__name__ = name
    return func

uppercase_letters = regex_check('uppercase_letters', 'A-Z')
uppercase_wchars  = regex_check('uppercase_wchars', 'A-Z0-9_')
uppercase_hex     = regex_check('uppercase_hex', '0-9A-F')

lowercase_letters = regex_check('lowercase_letters', 'a-z')
lowercase_wchars  = regex_check('lowercase_wchars', 'a-z0-9_')
lowercase_hex     = regex_check('lowercase_hex', '0-9a-f')

digits_str        = regex_check('digits_str', '0-9')

absolute_http_url = Field(
    type = str,
    check = SourceCodeTemplate(
        "$re.search(r'^https?://.{{1,2000}}$',{})",
        re = re,
    ),
)

#----------------------------------------------------------------------------------------------------------------------------------
# other field def utils

def one_of(*values):
    if len(values) == 0:
        raise ValueError('one_of requires arguments')
    type = values[0].__class__
    for v in values[1:]:
        if v.__class__ is not type:
            raise ValueError("All arguments to one_of should be of the same type (%s is not %s)" % (
                type.__name__,
                v.__class__.__name__,
            ))
    values = frozenset(values)
    return Field(
        type = type,
        check = values.__contains__,
    )

def nullable(fdef, default=None):
    return compile_field_def(fdef).derive(
        nullable = True,
        default = default,
    )

#----------------------------------------------------------------------------------------------------------------------------------
