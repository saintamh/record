#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
$Id: $
Herve Saint-Amand
Edinburgh
"""

#----------------------------------------------------------------------------------------------------------------------------------

# Because Records are dynamically created classes that are compiled within a function, 'pickle' cannot find the class definition by
# name alone. For this reason we need to keep a register here of all Record classes that have been created, indexed by name.
#
# This is rather hacky, and has a few implications: you shouldn't create millions of record classes, as they'll all be referenced
# here, and you can't create two record classes with the same name. The latter could come back to bite me some day. I'm not sure
# what I'll do then.

ALL_RECORDS = {}

def register_class_for_unpickler (cls_name, cls):
    ALL_RECORDS[cls_name] = cls

class RecordUnpickler (object):
    def __init__ (self, cls_name):
        self.cls_name = cls_name
    def __call__ (self, *values):
        return ALL_RECORDS[self.cls_name](*values)

#----------------------------------------------------------------------------------------------------------------------------------