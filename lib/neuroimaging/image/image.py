import os, string, types
import numpy as N

import utils
import pipes
import enthought.traits as traits

from neuroimaging.reference import grid, axis, mapping
spaceaxes = axis.space


class Image(traits.HasTraits):

    nslicedim = traits.Int(2)
    shape = traits.ListInt()
    spatial_shape = traits.ListInt()
    start = traits.ListFloat()
    step = traits.ListFloat()

    def __init__(self, image, pipe=None, **keywords):
        '''
        Create a Image (volumetric image) object from either a file, an existing Image object, or an array.
        '''

        traits.HasTraits.__init__(self, **keywords)

        if isinstance(image, Image):
            self.image = image.image
            self.isfile = image.isfile
        elif not pipe:
            if isinstance(image, N.ndarray) or isinstance(image, N.core.memmap):
                self.isfile = False
                self.image = pipes.ArrayPipe(image, **keywords)
            elif type(image) == types.StringType:
                self.isfile = True
                pipe = pipes.URLPipe(image, **keywords)
                self.image = pipe.getimage(**keywords)
##             elif type(image) in [types.ListType, types.TupleType]:
##                 self.image = pipes.ListPipe(image, **keywords)
##                 self.isfile = True # just in case any are files, we should try to open/close them
        else:
            self.image = pipe(image, **keywords)
            self.isfile = image.isfile
            
        self.type = type(self.image)

        # Find spatial grid -- this is the one that will be used generally

        self.grid = self.image.grid
        self.shape = list(self.grid.shape)
        self.ndim = len(self.shape)

    def __del__(self):
        if self.isfile:
            try:
                self.image.close()
            except:
                pass
        else:
            del(self.image)

    def open(self, mode='r'):
        if self.isfile:
            self.image.open(mode=mode)

    def close(self):
        if self.isfile:
            try:
                self.image.close()
            except:
                pass
        
    def __iter__(self):
        """
        Create an iterator over an image based on its grid's iterator.
        """
        iter(self.grid)

        if isinstance(self.grid.iterator, grid.ParcelIterator) or isinstance(self.grid.iterator, grid.SliceParcelIterator):
            if hasattr(self.image, 'memmap'):
                self.buffer = self.image.memmap
            elif isinstance(self.image.data, N.ndarray):
                self.buffer = self.image.data
            self.buffer.shape = N.product(self.buffer.shape)
        return self

    def next(self, value=None, data=None):
        """
        The value argument here is used when, for instance one wants to
        iterate over one image with a ParcelIterator and write out data
        to this image without explicitly setting this image\'s grid to
        the original image\'s grid, i.e. to just take the value the
        original image\'s iterator returns and use it here.
        """
        if value is None:
            self.itervalue = self.grid.next()
            value = self.itervalue

        itertype = value.type

        if itertype is 'slice':
            if data is None:
                return_value = N.squeeze(self.getslice(value.slice))
                if hasattr(self, 'postread'):
                    return self.postread(return_value)
                else:
                    return return_value
            else:

                self.writeslice(value.slice, data)

        elif itertype is 'parcel':
            if data is None:
                value.where.shape = N.product(value.where.shape)
                self.label = value.label
                return_value = self.buffer.compress(value.where, axis=0)
                if hasattr(self, 'postread'):
                    return self.postread(return_value)
                else:
                    return return_value
            else:
                indices = N.nonzero(value.where)
                self.buffer.put(data, indices)

        elif itertype == 'slice/parcel':
            if data is None:
                tmp = self.getslice(value.slice)
                return_value = tmp.compress(value.where)
                if hasattr(self, 'postread'):
                    return self.postread(return_value)
                else:
                    return return_value
            else:
                indices = N.nonzero(value.where)
                self.buffer.put(data, indices)
                

    def getvoxel(self, voxel):
        if len(voxel) != self.ndim:
            raise ValueError, 'expecting a voxel coordinate'
        return self.getslice(voxel)

    def toarray(self, clean=True, **keywords):
        '''Return a Image instance that has an ArrayPipe as its image attribute.

        >>> from numpy import *
        >>> from BrainSTAT import *
        >>> test = Image(testfile('anat+orig.HEAD'))
        >>> _test = test.toarray()
        >>> print _test.image.data.shape
        (124, 256, 256)
        >>> test = Image(testfile('test_fmri.img'))
        >>> _test = test.toarray(slice=(2,), grid=test.grid)
        >>> print _test.shape
        (13, 128, 128)
        '''

        if self.isfile:
            self.close()

        if clean:
            _clean = N.nan_to_num
            _data = _clean(self.readall(**keywords))
        else:
            _data = self.readall(**keywords)

        if hasattr(self, 'postread'):
            _data = self.postread(_data)
        return Image(_data, grid=self.grid, **keywords)

    def tofile(self, filename, array=True, **keywords):
        outimage = Image(filename, mode='w', grid=self.grid, **keywords)

        if array:
            tmp = self.toarray(**keywords)
            outimage.image.writeslice(slice(0,self.grid.shape[0],1), tmp.image.data)
        else:
            tmp = iter(self)
            outimage = iter(outimage)
            for dataslice in tmp:
                outimage.next(data=dataslice)
                
        outimage.close()
        
        return outimage

    fill = traits.Float(0.0)
    
    def readall(self, clean=False, **keywords): 
        '''
        Read an entire Image object, returning a numpy, not another instance of Image. By default, it does not read 4d images. Missing values are filled in with the value of fill (default=self.fill=0.0).
        '''

        try:
            _slice = self.grid.iterator.allslice
        except:
            _slice = slice(0, self.shape[0], 1)
        value = self.image.getslice(_slice)

        if clean:
            value = Image(_clean(value, fill=self.fill))
        return value

    def getslice(self, slice):
        return self.image.getslice(slice)

    def writeslice(self, slice, data):
        return self.image.writeslice(slice, data)

    def check_grid(self, test):
        return self.grid == test.grid

class ImageSequenceIterator(traits.HasTraits):

    """
    Take a sequence of images, and an optional grid (which defaults to imgs[0].grid) and
    create an iterator whose next method returns array with shapes

    (len(imgs),) + self.imgs[0].next().shape

    Very useful for voxel-based methods, i.e. regression, one-sample t.

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