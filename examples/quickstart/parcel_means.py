#!/bin/env python
'''
Extract the means from different parcels within a functional dataset;
show use of iterators in image to do this.  Show use of region
iterators

Usage:
parcel_means.py
'''

import numpy as N
import pylab

from neuroimaging.modalities.fmri import fMRIImage
from neuroimaging.utils.tests.data import repository

subject_no=0
run_no = 1
func_img = fMRIImage('FIAC/fiac%d/fonc%d/fsl/filtered_func_data.img' %
                     (subject_no, run_no),
                     datasource=repository)

# Create array of same shape as one time point of functional image
parcel_arr = N.zeros(func_img.grid.shape[1:])

# Create 2 pretend parcels in array at middle, and off-centre
offset=5
middle_block_def = [slice(i/2-offset, i/2+offset, 1) for i in parcel_arr.shape]
parcel_arr[middle_block_def] = 1
off_block_def = [slice(i/2-2*offset, i/2-offset, 1) for i in parcel_arr.shape]
parcel_arr[off_block_def] = 2

# Set up parcel iteration for functional image
func_img.grid.set_iter_param("itertype", 'parcel')
func_img.grid.set_iter_param("parcelmap", parcel_arr[:])
func_img.grid.set_iter_param("parcelseq", [1, 2])

# Iterate to collect means over parcels in functional image
means = {}
for d in func_img:
    means[func_img.label] = N.mean(d, axis=1)

# Now iterate over regions
func_img.grid.parcelseq = [0, 2] # changing the parcelseq to select "regions"
for d in func_img:
    print d.shape

pylab.plot(means[(1,)], means[(2,)], 'bo')
pylab.show()