#!/bin/bash

# $Id: $
# Herve Saint-Amand
# Edinburgh

#------------------------------------------------------------------------------

cd $(dirname $0)

for v in 2 3; do
    (python$v -m tests.run $* || exit $?) 2>&1 \
        | sed "s/^/PY$v: /"
    echo
done

#------------------------------------------------------------------------------
