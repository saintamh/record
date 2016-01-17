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
from collections import Counter
import re
from sys import argv

# this module
from . import check_tests
from . import coercion_tests
from . import coll_tests
from . import core_tests
from . import json_tests
from . import pickle_tests
from . import shortcut_tests

#----------------------------------------------------------------------------------------------------------------------------------

ALL_TEST_MODS = (
    check_tests,
    coercion_tests,
    coll_tests,
    core_tests,
    json_tests,
    pickle_tests,
    shortcut_tests,
)

def iter_all_tests(selected_mod_name):
    mod_name = lambda mod: re.sub (r'.+\.', '', re.sub (r'_tests$', '', mod.__name__))
    found = False
    for mod in ALL_TEST_MODS:
        if selected_mod_name in (None,mod_name(mod)):
            found = True
            for test in mod.ALL_TESTS:
                yield test
    if selected_mod_name and not found:
        raise Exception ("Module '%s' not found. Available modules:\n%s" % (
            selected_mod_name,
            ''.join (
                '\n\t%s' % mod_name(mod)
                for mod in ALL_TEST_MODS,
            ),
        ))

#----------------------------------------------------------------------------------------------------------------------------------

def main (selected_mod_name=None):
    tally = Counter()
    all_tests = tuple(iter_all_tests(selected_mod_name))
    test_id_fmt = "{{:.<{width}}}".format (width = 3 + max (len(test_id) for test_id,test_func in all_tests))
    result_fmt = "[{:^4}] {}"
    for test_id,test_func in all_tests:
        tally['total'] += 1
        print test_id_fmt.format(test_id+' '),
        try:
            test_func()
        except Exception, ex:
            raise
            print result_fmt.format ('FAIL', '{}: {}'.format(ex.__class__.__name__, ex))
            tally['failed'] += 1
        else:
            print result_fmt.format ('OK', '')
            tally['passed'] += 1
    print
    for item in sorted (tally.items()):
        print "{}: {}".format(*item)

if __name__ == '__main__':
    main(*argv[1:])

#----------------------------------------------------------------------------------------------------------------------------------