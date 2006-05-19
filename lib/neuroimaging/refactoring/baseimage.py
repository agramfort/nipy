"""
BaseImage class - wrapper for Image class to test changes to Image interface
"""


import sys, os, types

from attributes import *
import numpy as N
import enthought.traits as traits

from neuroimaging.data import DataSource
from neuroimaging.image.formats import getreader
from neuroimaging.reference import axis, mapping
from neuroimaging.reference.grid import SamplingGrid, IdentityGrid
from neuroimaging.reference.grid_iterators import ParcelIterator, SliceParcelIterator

##############################################################################
class Image(traits.HasTraits):

    #-------------------------------------------------------------------------
    def __del__(self): del self.image


##############################################################################
class BaseImage(object):
    "Base class for all image objects.  Is constructed from an ndarray."

    #---------------------------------------------
    #   Attributes
    #---------------------------------------------
   
    class array (attribute):
        "raw unresampled data array"
        implements=N.ndarray

    class grid (attribute):
        "image resampling grid"
        implements=SamplingGrid
        def init(_,self): return IdentityGrid(self.array.shape)

    class shape (readonly):
        "image shape"
        def get(_, self): return self.grid.shape

    class ndim (readonly):
        "number of image dimensions"
        def get(_, self): return len(self.shape)

    class ismemmapped (readonly):
        "is the internal array a memory map?"
        def get(_, self): return isinstance(self.array, numpy.memmap)

    deferto(grid, ("transform",))

    #---------------------------------------------
    #   Static Methods
    #---------------------------------------------

    @staticmethod
    def fromfile(filename, **kwargs):
        return getreader(filename)(filename, **kwargs)

    #---------------------------------------------
    #   Instance Methods
    #---------------------------------------------

    def __init__(self, arr, grid=None):
        self.array = arr
        if grid is not None: self.grid = grid
    def __getitem__(self, slices): return self.get_slice(slices)
    def __setitem__(self, slices, data): self.write_slice(slices, data)

    def grid_array(self): 
        '''
        Read an entire Image object, returning a numpy array. By
        default, it does not read 4d images. 
        '''
        # NB - this used to be the readall method of the Image class
        # We may need port old code from this usage in due course
        # CHECK THAT: all grid iterators should have allslice attribute
        return self.get_slice(self.grid.iterator.allslice)

    def get_slice(self, slices): return self.array[slices]

    def write_slice(self, slices, data): self.array[slices] = data

    def apply_transform(self, matrix): self.grid.apply_transform

    #-------------------------------------------------------------------------
    def __iter__(self):
        "Create an iterator over an image based on its grid's iterator."
        iter(self.grid)
        if isinstance(self.grid.iterator, ParcelIterator) or \
           isinstance(self.grid.iterator, SliceParcelIterator):
            self.array.shape = N.product(self.buffer.shape)
        return self

    #-------------------------------------------------------------------------
    def compress(self, where, axis=0):
        return self.array.compress(where, axis=axis)

    #-------------------------------------------------------------------------
    def put(self, data, indices):
        return self.array.put(data, indices)

    #-------------------------------------------------------------------------
    def next(self, value=None, data=None):
        """
        The value argument here is used when, for instance one wants to
        iterate over one image with a ParcelIterator and write out data to
        this image without explicitly setting this image's grid to the
        original image's grid, i.e. to just take the value the original
        image's iterator returns and use it here.
        """
        if value is None: self.itervalue = value = self.grid.next()
        itertype = value.type
        postread = getattr(self, 'postread', None) or (lambda x:x)

        if data is None:
            if itertype is 'slice':
                return postread(N.squeeze(self.getslice(value.slice)))
            elif itertype is 'parcel':
                value.where.shape = N.product(value.where.shape)
                self.label = value.label
                return postread(self.compress(value.where, axis=0))
            elif itertype == 'slice/parcel':
                return postread(self.getslice(value.slice).compress(value.where))
        else:
            if itertype is 'slice':
                self.writeslice(value.slice, data)
            elif itertype is 'parcel':
                indices = N.nonzero(value.where)
                self.put(data, indices)
            elif itertype == 'slice/parcel':
                indices = N.nonzero(value.where)
                self.put(data, indices)
                
    #-------------------------------------------------------------------------
    def getvoxel(self, voxel):
        if len(voxel) != self.ndim:
            raise ValueError("expecting a voxel coordinate")
        return self.getslice(voxel)

    #-------------------------------------------------------------------------
    def tofile(self, filename, array=True, **keywords):
        outimage = Image(filename, mode='w', grid=self.grid, **keywords)
        if array:
            tmp = self.toarray(**keywords)
            outimage.image.writeslice(slice(0,self.grid.shape[0],1), tmp.image.data)
        else:
            outimage = iter(outimage)
            for dataslice in self: outimage.next(data=dataslice)
        outimage.close()
        return outimage

#-----------------------------------------------------------------------------
def image(input, datasource=DataSource()):
    """
    Create a Image (volumetric image) object from either a file, an
    existing Image object, or an array.
    """
    
    # from array
    if isinstance(input, N.ndarray): return BaseImage(input)
        
    # from filename or url
    elif type(input) == types.StringType:
        return BaseImage.fromfile(input, datasource=datasource)


def writebrick(outfile, start, data, shape, offset=0, outtype=None, byteorder=sys.byteorder, return_tell = True):
    """from Utils """
    if return_tell:
        try: startpos = outfile.tell()
        except:
            outfile = file(outfile.name, 'rb+')
            startpos = 0
    if outtype: outdata = data.astype(outtype)
    else:
        outdata = data
        outtype = outdata.dtype
    if byteorder != sys.byteorder: outdata.byteswap()
    outdata.shape = (N.product(outdata.shape),)
    count = data.shape
    ndim = len(shape)

    # How many dimensions are "full" slices
    nslicedim = 0
    i = ndim - 1
    while count[i] is shape[i] and i >= 0:
        nslicedim = nslicedim + 1
        i = i - 1

    if nslicedim:
        nslice = N.product(shape[(ndim - nslicedim):])
    else:
        nslice = count[:-1]
        nslicedim = 1

    nloopdim = ndim - nslicedim
    test = N.product(N.less_equal(N.array(start) + N.array(count), N.array(shape)))
    if not test: raise ValueError, 'start+count not <= shape'
    nloop = N.product(count[nloopdim:])
    nskip = N.product(shape[nloopdim:])
    ntotal = N.product(count)
    elsize = outdata.dtype.itemsize
    shape_reverse = list(shape)
    shape_reverse.reverse()
    strides = [1] + list(N.multiply.accumulate(shape_reverse)[:-1])
    strides.reverse()
    strides = N.array(strides, N.Int64)
    strides = strides * elsize
    outfile.seek(offset + N.add.reduce(start * strides))
    index = 0
    while index < ntotal:
        outdata[index:(index+nloop)].tofile(outfile)
        outfile.seek((nskip - nloop) * elsize, 1)
        index = index + nloop
    if return_tell:
        outfile.seek(startpos, 0)
    outfile.flush()
    del(outdata)


##############################################################################
class ImageSequenceIterator(traits.HasTraits):
    """
    Take a sequence of images, and an optional grid (which defaults to
    imgs[0].grid) and create an iterator whose next method returns array
    with shapes (len(imgs),) + self.imgs[0].next().shape.  Very useful for
    voxel-based methods, i.e. regression, one-sample t.
    """
    def __init__(self, imgs, grid=None, **keywords):
        self.imgs = imgs
        if grid is None:
            self.grid = iter(self.imgs[0].grid)
        else:
            self.grid = iter(grid)

    def __iter__(self):
        return self

    def next(self, value=None):
        if value is None:
            value = self.grid.next()
        v = []
        for i in range(len(self.imgs)):
            v.append(self.imgs[i].next(value=value))
        return N.array(v, N.Float)

