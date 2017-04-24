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
from datetime import datetime, timedelta
from decimal import Decimal

# this module
from .. import *
from .plumbing import *

#----------------------------------------------------------------------------------------------------------------------------------
# init

ALL_TESTS,test = build_test_registry()

#----------------------------------------------------------------------------------------------------------------------------------
# sanity

@test("scalar fields are directly rendered to a PODS")
def _():
    class R(Record):
        id = str
        label = unicode
        age = int
        salary = float
    r = R(id='robert', label=u"Robert Smith", age=42, salary=12.70)
    d = r.record_pods()
    assert_eq(d, {
        "id": "robert",
        "label": "Robert Smith",
        "age": 42,
        "salary": 12.70,
    })

@test("nested records are rendered to a PODS as nested objects")
def _():
    class Name(Record):
        first = unicode
        last = unicode
    class Person(Record):
        name = Name
        age = int
    p = Person(name=Name(first=u"Robert",last=u"Smith"), age=100)
    d = p.record_pods()
    assert_eq(d, {
        "name": {
            "first": "Robert",
            "last": "Smith",
        },
        "age": 100,
    })

#----------------------------------------------------------------------------------------------------------------------------------
# type-specific tests

def _other_record():
    class R2(Record):
        v = int
    return R2

@foreach(
    (cls_name, cls, val, nullable_or_not)
    for cls_name,cls,non_null_val in (
        ('str', str, '\xE2\x9C\x93\'\\\"\xE2\x9C\x93'),
        ('unicode', unicode, u'Herv\u00E9\'\\\"Herv\u00E9'),
        ('ascii-only unicode', unicode, u'ASCII'),
        ('int', int, 42),
        ('long', long, 42L),
        ('float', float, 0.3),
        ('sequence (nonempty)', seq_of(int), (1,2,3)),
        ('sequence (empty)', seq_of(int), []),
        ('set (nonempty)', set_of(int), (1,2,3)),
        ('set (empty)', set_of(int), []),
        ('dict (nonempty)', dict_of(str,int), {'one':1,'two':2}),
        ('dict (empty)', dict_of(str,int), []),
        ('datetime', datetime, datetime(2016, 4, 15, 10, 01, 59)),
        ('timedelta', timedelta, timedelta(days=1, hours=2, minutes=3, seconds=4)),
        (lambda R2: ('other record', R2, R2(2)))(_other_record()),
    )
    for nullable_or_not,vals in (
        (lambda f: f, (non_null_val,)),
        (nullable, (non_null_val,None)),
    )
    for val in vals
)
def _(cls_name, cls, val, nullable_or_not):

    @test("Record with {}{} field (set to {!r}) -> PODS -> Record".format(
        'nullable ' if nullable_or_not is nullable else '',
        cls_name,
        val,
    ))
    def _():
        class R(Record):
            field = nullable_or_not(cls)
        r1 = R(field=val)
        d = r1.record_pods()
        assert_isinstance(d, dict)
        try:
            r2 = R.from_pods(d)
            assert_eq(r1.field, r2.field)
        except Exception:
            print
            print "PODS: %r" % d
            raise

# @test("2016-04-15 - weird bug with serializing null values?")
# def _():
#     Item = record (
#         'Item',
#         one = nullable(unicode),
#         two = seq_of(int),
#     )
#     Collection = record ('Collection', items=seq_of(Item))
#     c = Collection([Item(one=None,two=[1,2,3])])
#     d = json.loads(c.json_dumps())
#     assert_eq (d, {
#         "items": [{
#             "two": [1,2,3]
#         }]
#     })

#----------------------------------------------------------------------------------------------------------------------------------
# duck-typing which classes can be serialized to PODS

@test("the nested object can be anything with a `record_pods' method")
def _():
    class Name(object):
        def __init__(self, first, last):
            self.first = first
            self.last = last
        def record_pods(self):
            return [self.first, self.last]
    class Person(Record):
        name = Name
        age = int
    p = Person(name=Name(first=u"Robert",last=u"Smith"), age=100)
    d = p.record_pods()
    assert_eq(d, {
        "name": ["Robert", "Smith"],
        "age": 100,
    })

@test("If a class has a member with no `record_pods' method, it can still be instantiated, but it can't be serialized to a PODS")
def _():
    Name = namedtuple('Name', ('name',))
    class R(Record):
        name = Name
    r = R(Name('peter'))
    with expected_error(CannotBeSerializedToPods):
        r.record_pods()

#----------------------------------------------------------------------------------------------------------------------------------
# duck-typing which classes can be deserialized from PODS

@test("anything with a `from_pods' method can be parsed from a PODS")
def _():
    class Name(object):
        def __init__(self, first, last):
            self.first = first
            self.last = last
        @classmethod
        def from_pods(cls, data):
            return cls(*data.split('/'))
        def __cmp__(self, other):
            return cmp(self.last, other.last) and cmp(self.first, other.first)
    class R(Record):
        name = Name
    assert_eq(
        R.from_pods({"name": "Arthur/Smith"}),
        R(Name("Arthur", "Smith")),
    )

@test("If a class has a member with no `from_pods' method, it can still be instantiated, but it can't be parsed from a PODS")
def _():
    Name = namedtuple('Name', ('name',))
    class R(Record):
        name = Name
    r = R(Name('peter'))
    class CantTouchThis(object):
        def __getattr__(self, attr):
            # ensure that the value given to `from_pods' below isn't even looked at in any way
            raise Exception("boom")
    with expected_error(CannotBeSerializedToPods):
        R.from_pods(CantTouchThis())

#----------------------------------------------------------------------------------------------------------------------------------
# collections

@test("sequence fields get serialized to plain lists")
def _():
    class R(Record):
        elems = seq_of(int)
    r = R(elems=[1,2,3])
    assert_eq(r.record_pods(), {
        "elems": [1,2,3],
    })

@test("pair fields get serialized to plain lists")
def _():
    class R(Record):
        elems = pair_of(int)
    r = R(elems=[1,2])
    assert_eq(r.record_pods(), {
        "elems": [1,2],
    })

@test("set_of fields get serialized to plain lists")
def _():
    class R(Record):
        elems = set_of(int)
    r = R(elems=[1,2,3])
    elems = r.record_pods()['elems']
    assert isinstance(elems, list), repr(elems)
    assert_eq(
        sorted(elems),
        [1,2,3],
    )

@test("dict_of fields get serialized to plain dicts")
def _():
    class R(Record):
        elems = dict_of(str,int)
    r = R(elems={'uno':1,'zwei':2})
    assert_eq(r.record_pods(), {
        "elems": {'uno':1,'zwei':2},
    })

@test("an empty dict gets serialized to '{}'")
def _():
    class R(Record):
        v = dict_of(str,str)
    assert_eq(R({}).record_pods(), {
        'v': {},
    })

#----------------------------------------------------------------------------------------------------------------------------------
# handling of null values

@test("null fields are not included in the a PODS")
def _():
    class R(Record):
        x = int
        y = nullable(int)
    r = R(x=1, y=None)
    d = r.record_pods()
    assert_eq(d, {'x':1})

@test("explicit 'null' values can be parsed from a PODS")
def _():
    class R(Record):
        x = int
        y = nullable(int)
    r0 = R(11)
    r1 = R.from_pods({"x":11})
    r2 = R.from_pods({"x":11, "y":None})
    assert_eq(r1, r0)
    assert_eq(r2, r0)
    assert_eq(r1, r2)

@test("if the field is not nullable, FieldNotNullable is raised when parsing an explicit null")
def _():
    class R(Record):
        x = int
        y = int
    with expected_error(FieldNotNullable):
        R.from_pods({"x":11,"y":None})

@test("if the field is not nullable, FieldNotNullable is raised when parsing an implicit null")
def _():
    class R(Record):
        x = int
        y = int
    with expected_error(FieldNotNullable):
        R.from_pods({"x":11})

#----------------------------------------------------------------------------------------------------------------------------------
# built-in marshallers

@foreach((
    (datetime(2009,10,28,8,53,2), "2009-10-28T08:53:02"),
    (Decimal('10.3'), "10.3"),
))
def _(obj, marshalled_str):

    @test("{} objects automatically get marshalled and unmarshalled as expected".format(obj.__class__.__name__))
    def _():
        class R(Record):
            fobj = obj.__class__
        r1 = R(obj)
        d = r1.record_pods()
        assert_eq(d, {"fobj": marshalled_str})
        assert_eq(r1, R.from_pods(d))

#----------------------------------------------------------------------------------------------------------------------------------
# custom marshallers

@test("fields can be serialized and deserialized using custom marshallers")
def _():
    Point = namedtuple('Point', ('x','y'))
    marshaller = Marshaller(
        lambda pt: '%d,%d' % pt,
        lambda s: Point(*map(int,s.split(','))),
    )
    with temporary_marshaller_registration(Point, marshaller):
        class R(Record):
            pt = Point
        r1 = R(Point(1,2))
        assert_eq(
            r1.record_pods(),
            {"pt": "1,2"},
        )
        assert_eq(
            R.from_pods(r1.record_pods()),
            r1,
        )

@test("the marshaller must be available when the class is compiled, not when record_pods() is called")
def _():
    Point = namedtuple('Point', ('x','y'))
    marshaller = Marshaller(
        lambda pt: '%d,%d' % pt,
        lambda s: Point(*map(int,s.split(','))),
    )
    class R(Record):
        pt = Point
    with expected_error(CannotBeSerializedToPods):
        R(Point(1,2)).record_pods()

#----------------------------------------------------------------------------------------------------------------------------------
