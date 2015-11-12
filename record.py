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
from collections import namedtuple
from functools import wraps
import re

# saintamh
from ..util.codegen import \
    ClassDefEvaluationNamespace, ExternalValue, SourceCodeGenerator, SourceCodeTemplate, \
    compile_expr

# this module
from .unpickler import RecordUnpickler, register_record_class_for_unpickler

#----------------------------------------------------------------------------------------------------------------------------------
# the `record' function and the `Field' data structure are the two main exports of this module

def record (cls_name, **field_defs):
    verbose = field_defs.pop ('__verbose', False)
    src_code_gen = RecordClassTemplate (cls_name, **field_defs)
    cls = compile_expr (src_code_gen, cls_name, verbose=verbose)
    register_record_class_for_unpickler (cls_name, cls)
    return cls

class Field (object):

    def __init__ (self, type, nullable=False, default=None, coerce=None, check=None):
        self.type = type
        self.nullable = nullable
        self.default = default
        self.coerce = coerce
        self.check = check

    def derive (self, nullable=None, default=None, coerce=None, check=None):
        return self.__class__ (
            type = self.type,
            nullable = self.nullable if nullable is None else nullable,
            default = self.default if default is None else default,
            coerce = self.coerce if coerce is None else coerce,
            check = self.check if check is None else check,
        )

    def __repr__ (self):
        return 'Field (%r%s%s%s%s)' % (
            self.type,
            ', nullable=True' if self.nullable else '',
            ', default=%r' % self.default if self.default else '',
            ', coerce=%r' % self.coerce if self.coerce else '',
            ', check=%r' % self.check if self.check else '',
        )

#----------------------------------------------------------------------------------------------------------------------------------
# public exception classes

class RecordsAreImmutable (TypeError):
    pass

class FieldError (ValueError):
    pass

class FieldValueError (FieldError):
    pass

class FieldTypeError (FieldError):
    pass

class FieldNotNullable (FieldValueError):
    pass

#----------------------------------------------------------------------------------------------------------------------------------

# So this module uses `exec' on a string of Python code in order to generate the new classes.
#
# This is ugly, goes against all received standard practice, and makes this module rather hard to read, and therefore hard to
# modify, though I've tried to keep things as tidy and readable as possible. The reason for this is simply performance. The
# previous incarnation of this module (called "struct.py") used Python's great meta-programming facilities, and it ran quite slow.
# Using strings allows us to unroll loops over a record's fields, to use Python's native parameter system instead of having globs
# everywhere, to evaluate conditionals ("is this field nullable?") at class creation time rather than at every constructor
# invocation, etc etc. Some quick benchmarks show that this runs about 6x faster than struct.py.
#
# The bottom line is that this class has a huge ratio of how often it is used over how often it is modified, so I find it
# acceptable to make it harder to maintain for the sake of performance.

class RecordClassTemplate (SourceCodeTemplate):

    template = '''
        class $cls_name (object):
            __slots__ = $slots

            def __init__ (self, $init_params):
                $field_checks
                $set_fields

            def __setattr__ (self, attr, value):
                raise $RecordsAreImmutable ("$cls_name objects are immutable")
            def __delattr__ (self, attr):
                raise $RecordsAreImmutable ("$cls_name objects are immutable")

            def json_struct (self):
                return {
                    $json_struct
                }

            def __repr__ (self):
                return "$cls_name ($repr_str)" % $values_as_tuple
            def __cmp__ (self, other):
                return $cmp_stmt
            def __hash__ (self):
                return $hash_expr

            def __reduce__ (self):
                return ($RecordUnpickler("$cls_name"), $values_as_tuple)
    '''

    def __init__ (self, cls_name, **field_defs):
        self.cls_name = cls_name
        self.field_defs = dict (
            (fname,compile_field_def(fdef))
            for fname,fdef in field_defs.items()
        )
        self.sorted_field_names = sorted (
            field_defs,
            key = lambda f: (self.field_defs[f].nullable, f),
        )
        for sym in (RecordsAreImmutable, RecordUnpickler):
            setattr (self, sym.__name__, ExternalValue(sym))

    def field_joiner_property (sep, prefix='', suffix=''):
        return lambda raw_meth: property (
            lambda self: Joiner (sep, prefix, suffix, (
                raw_meth (self, i, f, self.field_defs[f])
                for i,f in enumerate(self.sorted_field_names)
            ))
        )

    @field_joiner_property ('', prefix='(', suffix=')')
    def slots (self, findex, fname, fdef):
        # NB trailing comma to ensure single val still a tuple
        return "{!r},".format(fname)

    @field_joiner_property ('', prefix='(', suffix=')')
    def values_as_tuple (self, findex, fname, fdef):
        # NB trailing comma here too, for the same reason
        return 'self.{},'.format (fname)

    @field_joiner_property (', ')
    def init_params (self, findex, fname, fdef):
        return '{}{}'.format (fname, '=None' if fdef.nullable else '')

    @field_joiner_property ('\n')
    def field_checks (self, findex, fname, fdef):
        return FieldHandlingStmtsTemplate (
            fdef,
            fname,
            expr_descr='{}.{}'.format(self.cls_name,fname)
        )

    @field_joiner_property ('\n')
    def set_fields (self, findex, fname, fdef):
        # you can cheat past our fake immutability by using object.__setattr__, but don't tell anyone
        return 'object.__setattr__ (self, "{0}", {0})'.format (fname)

    @field_joiner_property (', ')
    def repr_str (self, findex, fname, fdef):
        return '{}=%r'.format(fname)

    @field_joiner_property (' or ')
    def cmp_stmt (self, findex, fname, fdef):
        return 'cmp(self.{0},other.{0})'.format(fname)

    @field_joiner_property (' + ')
    def hash_expr (self, findex, fname, fdef):
        return 'hash(self.{fname})*{mul}'.format (
            fname = fname,
            mul = 7**findex,
        )

    @field_joiner_property (',\n')
    def json_struct (self, findex, fname, fdef):
        if hasattr (fdef.type, 'json_struct'):
            json_value_expr = 'self.{fname}.json_struct() if self.{fname} is not None else None'.format (fname=fname)
        else:
            json_value_expr = 'self.{fname}'.format (fname=fname)
        return '{fname!r}: {json_value_expr}'.format (
            fname = fname,
            json_value_expr = json_value_expr
        )

#----------------------------------------------------------------------------------------------------------------------------------

class FieldHandlingStmtsTemplate (SourceCodeTemplate):
    """
    Given one field, this generates all constructor statements that relate to that one field: checks, default values, coercion,
    etc. This is inserted both into the constructor of the Record class, as well as in the constructor of the various collection
    types (seq_of etc), which also must check the value and type of their elements.
    """

    KNOWN_COERCE_FUNCTIONS_THAT_NEVER_RETURN_NONE = frozenset ((
        int, long, float,
        str, unicode,
        bool,
    ))

    template = '''
        try:
            $default_value
            $coerce
            $null_check
            $value_check
            $type_check
        except $FieldError, err:
            from sys import exc_info
            exc_type, exc_mesg, exc_tb = exc_info()
            raise exc_type, "$expr_descr%s" % exc_mesg, exc_tb
    '''

    def __init__ (self, fdef, var_name, expr_descr):
        self.fdef = fdef
        self.var_name = var_name
        self.expr_descr = expr_descr
        self.fdef_type = ExternalValue(fdef.type)
        self.fdef_type_name = fdef.type.__name__
        for sym in (FieldError, FieldTypeError, FieldValueError, FieldNotNullable):
            setattr (self, sym.__name__, ExternalValue(sym))

    @property
    def default_value (self):
        if self.fdef.nullable and self.fdef.default is not None:
            return '''
                if $var_name is None:,
                    $var_name = $default_expr
            '''

    @property
    def default_expr (self):
        return ExternalValue(self.fdef.default)

    @property
    def coerce (self):
        if self.fdef.coerce is not None:
            return '$var_name = $coerce_invocation'

    @property
    def coerce_invocation (self):
        return ExternalCodeInvocation (self.fdef.coerce, self.var_name)

    @property
    def null_check (self):
        if not self.fdef.nullable and self.fdef.coerce not in self.KNOWN_COERCE_FUNCTIONS_THAT_NEVER_RETURN_NONE:
            return '''
                if $var_name is None:
                    raise $FieldNotNullable (" cannot be None")
            '''

    @property
    def value_check (self):
        if self.fdef.check is not None:
            return '''
                if not $check_invocation:
                    raise $FieldValueError(" %r is not a valid value" % ($var_name,))
            '''

    @property
    def check_invocation (self):
        return ExternalCodeInvocation (self.fdef.check, self.var_name)

    @property
    def type_check (self):
        if self.fdef.coerce is not self.fdef.type:
            return '''
                if $not_null_and not isinstance ($var_name, $fdef_type):
                    raise $FieldTypeError (" should be of type $fdef_type_name, not %s" % $var_name.__class__.__name__)
            '''

    @property
    def not_null_and (self):
        if self.fdef.nullable:
            return '$var_name is not None and '

#----------------------------------------------------------------------------------------------------------------------------------
# other field def utils

def one_of (*values):
    if len(values) == 0:
        raise ValueError ('one_of requires arguments')
    type = values[0].__class__
    for v in values[1:]:
        if v.__class__ is not type:
            raise ValueError ("All arguments to one_of should be of the same type (%s is not %s)" % (
                type.__name__,
                v.__class__.__name__,
            ))
    values = frozenset (values)
    return Field (
        type = type,
        check = values.__contains__,
    )

def nullable (fdef):
    return compile_field_def(fdef).derive (
        nullable = True,
    )

#----------------------------------------------------------------------------------------------------------------------------------
# code-generation utils (private)

def compile_field_def (fdef):
    if isinstance(fdef,Field):
        return fdef
    else:
        return Field(fdef)

class ExternalCodeInvocation (SourceCodeGenerator):
    def __init__ (self, code_ref, param_name):
        self.code_ref = code_ref
        self.param_name = param_name
    def expand (self, ns):
        if isinstance (self.code_ref, basestring):
            if not re.search (
                    # Avert your eyes. This checks that there is one and only one '{}' in the string. Escaped {{ and }} are allowed
                    r'^(?:[^\{\}]|\{\{|\}\})*\{\}(?:[^\{\}]|\{\{|\}\})*',
                    self.code_ref,
                    ):
                raise ValueError (self.code_ref)
            return '({})'.format (self.code_ref.format (self.param_name))
        elif hasattr (self.code_ref, '__call__'):
            return '{coerce_sym}({param_name})'.format (
                coerce_sym = ns.intern (self.code_ref),
                param_name = self.param_name,
            )
        else:
            raise ValueError (repr(self.code_ref))

# not sure where this belongs
class Joiner (SourceCodeGenerator):
    def __init__ (self, sep, prefix, suffix, values):
        self.sep = sep
        self.prefix = prefix
        self.suffix = suffix
        self.values = values
    def expand (self, ns):
        return '{prefix}{body}{suffix}'.format (
            prefix = self.prefix,
            suffix = self.suffix,
            body = self.sep.join (
                # There's a similar isinstance check in SourceCodeTemplate.lookup. Feels like I'm missing some elegant way of
                # unifying these two.
                v.expand(ns) if isinstance(v,SourceCodeGenerator) else str(v)
                for v in self.values
            ),
        )

#----------------------------------------------------------------------------------------------------------------------------------
