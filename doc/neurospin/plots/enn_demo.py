# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
import numpy as np
x = np.c_[np.random.normal(size=1e4), 
          np.random.normal(scale=4, size=1e4)]

from nipy.neurospin.utils.emp_null import ENN
enn = ENN(x)
enn.threshold(verbose=True)

