#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
$Id: $
Herve Saint-Amand
Edinburgh
"""

#----------------------------------------------------------------------------------------------------------------------------------
# includes

# saintamh
from ..util.codegen import ClassDefEvaluationNamespace, SourceCodeTemplate, compile_expr
from ..util.coll import ImmutableDict
from ..util.strings import ucfirst

# this module
from .basics import Field, FieldValueError
from .record import FieldHandlingStmtsTemplate
from json_decoder import JsonDecoderMethodsForDictTemplate, JsonDecoderMethodsForSeqTemplate
from json_encoder import JsonEncoderMethodsForDictTemplate, JsonEncoderMethodsForSeqTemplate
from .unpickler import RecordUnpickler, register_class_for_unpickler
from .utils import compile_field_def

#----------------------------------------------------------------------------------------------------------------------------------
# Collection fields are instances of an appropriate subclass of tuple, frozenset, or ImmutableDict. This is the template used to
# generate these subclasses

class CollectionTypeCodeTemplate (SourceCodeTemplate):

    template = '''
        class $cls_name ($superclass):

            def $constructor (cls_or_self, iter_elems):
                return $superclass.$constructor (cls_or_self, $cls_name.check_elems(iter_elems))

            @staticmethod
            def check_elems (iter_elems):
                $check_elems_body

            $json_decoder_methods

            $json_encoder_methods

            # __repr__, __cmp__ and __hash__ are left to the superclass to implement

            def __reduce__ (self):
                return ($RecordUnpickler("$cls_name"), ($superclass(self),))
    '''

    RecordUnpickler = RecordUnpickler

#----------------------------------------------------------------------------------------------------------------------------------
# Subclasses of the above template, one per type

class SequenceCollCodeTemplate (CollectionTypeCodeTemplate):

    superclass = tuple
    constructor = '__new__'
    cls_name_suffix = 'Seq'

    def __init__ (self, elem_fdef):
        self.cls_name = ucfirst(elem_fdef.type.__name__) + self.cls_name_suffix
        self.json_decoder_methods = JsonDecoderMethodsForSeqTemplate (elem_fdef)
        self.json_encoder_methods = JsonEncoderMethodsForSeqTemplate (elem_fdef)
        self.elem_check_impl = FieldHandlingStmtsTemplate (
            elem_fdef,
            'elem',
            expr_descr='[elem]',
        )

    check_elems_body = '''
        for elem in iter_elems:
            $elem_check_impl
            yield elem
    '''

class PairCollCodeTemplate (SequenceCollCodeTemplate):
    FieldValueError = FieldValueError
    cls_name_suffix = 'Pair'
    check_elems_body = '''
        num_elems = 0
        for i,elem in enumerate(iter_elems):
            if i > 1:
                raise $FieldValueError ("A pair cannot have more than two elements")
            num_elems = i+1
            $elem_check_impl
            yield elem
        if num_elems != 2:
            raise $FieldValueError ("A pair must have two elements, not %d" % num_elems)        
    '''

class SetCollCodeTemplate (SequenceCollCodeTemplate):
    superclass = frozenset
    cls_name_suffix = 'Set'

class DictCollCodeTemplate (CollectionTypeCodeTemplate):
    superclass = ImmutableDict
    constructor = '__init__'

    def __init__ (self, key_fdef, val_fdef):
        self.cls_name = '{}To{}Dict'.format (
            ucfirst (key_fdef.type.__name__),
            ucfirst (val_fdef.type.__name__),
        )
        self.key_handling_stmts = FieldHandlingStmtsTemplate (key_fdef, 'key', expr_descr='<key>')
        self.val_handling_stmts = FieldHandlingStmtsTemplate (val_fdef, 'val', expr_descr='<val>')
        self.json_decoder_methods = JsonDecoderMethodsForDictTemplate (key_fdef, val_fdef)
        self.json_encoder_methods = JsonEncoderMethodsForDictTemplate (key_fdef, val_fdef)

    check_elems_body = '''
        for key,val in getattr (iter_elems, "iteritems", iter_elems.__iter__)():
            $key_handling_stmts
            $val_handling_stmts
            yield key,val
    '''

#----------------------------------------------------------------------------------------------------------------------------------

def make_coll (templ, verbose=False):
    coll_cls = compile_expr (templ, templ.cls_name, verbose=verbose)
    register_class_for_unpickler (templ.cls_name, coll_cls)
    return Field (
        coll_cls,
        coerce = lambda elems: coll_cls(elems) if elems is not None else None,
    )

# NB there's no reason for the dunder in "__verbose", except that it makes it the same as in the call to `record', where it *is*
# needed.

def seq_of (elem_fdef, __verbose=False):
    return make_coll (SequenceCollCodeTemplate(compile_field_def(elem_fdef)), verbose=__verbose)

def pair_of (elem_fdef, __verbose=False):
    return make_coll (PairCollCodeTemplate(compile_field_def(elem_fdef)), verbose=__verbose)

def set_of (elem_fdef, __verbose=False):
    return make_coll (SetCollCodeTemplate(compile_field_def(elem_fdef)), verbose=__verbose)

def dict_of (key_fdef, val_fdef, __verbose=False):
    return make_coll (DictCollCodeTemplate(compile_field_def(key_fdef), compile_field_def(val_fdef)), verbose=__verbose)

#----------------------------------------------------------------------------------------------------------------------------------
