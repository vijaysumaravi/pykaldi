import sys
import os

# This is needed for extension libs to be able to load each other.
sys.path.append(os.path.dirname(__file__))

from . import _str

# Absolute import of matrix_common does not work on Python 3 for some reason.
# Symbols in matrix_common are assigned to module importlib._bootstrap ????
import matrix_common
from matrix_common import MatrixResizeType, MatrixTransposeType

import kaldi_vector
from kaldi_vector import ApproxEqualVector, AssertEqualVector, VecVec

import kaldi_matrix
# from kaldi_matrix import *

import kaldi_matrix_ext
import numpy

import matrix_functions
from matrix_functions import *

# For Python 2/3 compatibility
try:
    xrange
except NameError:
    xrange = range

################################################################################
# Define Vector and Matrix Classes
################################################################################

class _VectorBase(object):
    """Base class defining the common additional Python API for vectors."""

    def clone(self):
        """Returns a copy of the vector."""
        return Vector(src=self)

    def copy_(self, src):
        """Copies data from src into this vector and returns this vector.

        Note: Source vector should have the same size as this vector.

        Args:
            src (Vector): Source vector to copy
        """
        self.CopyFromVec(src)
        return self

    def equal(self, other, tol=1e-16):
        """Checks if vectors have the same size and data within tolerance."""
        return self.ApproxEqual(other, tol)

    def numpy(self):
        """Returns this vector as a numpy ndarray."""
        return kaldi_matrix_ext.vector_to_numpy(self)

    def range(self, offset, length):
        """Returns a new subvector (a range of elements) of the vector."""
        return SubVector(self, offset, length)

    def __repr__(self):
        return str(self)

    def __str__(self):
        # All strings are unicode in Python 3, while we have to encode unicode
        # strings in Python2. If we can't, let python decide the best
        # characters to replace unicode characters with.
        # Below implementation was taken from
        # https://github.com/pytorch/pytorch/blob/master/torch/tensor.py
        if sys.version_info > (3,):
            return _str._vector_str(self)
        else:
            if hasattr(sys.stdout, 'encoding'):
                return _str._vector_str(self).encode(
                    sys.stdout.encoding or 'UTF-8', 'replace')
            else:
                return _str._vector_str(self).encode('UTF-8', 'replace')


class Vector(kaldi_vector.Vector, _VectorBase):
    """Python wrapper for kaldi::Vector<float>"""

    def __init__(self, size=None, src=None):
        """Creates a new vector.

        If no arguments are given, returns a new empty vector.
        If 'size' is given, returns a new vector of given size.
        If 'src' is given, returns a new vector that is a copy of the source.
        Note: 'size' and 'src' cannot be given at the same time.

        Args:
            size (int): Size of the new vector.
            src (Vector or ndarray): Source vector or 1-D numpy array to copy.
        """
        if src is not None and size is not None:
            raise TypeError("Vector arguments 'size' and 'src' "
                            "cannot be given at the same time.")
        super(Vector, self).__init__()
        if size is not None:
            if isinstance(size, int) and size >= 0:
                self.resize_(size, MatrixResizeType.UNDEFINED)
            else:
                raise TypeError("Vector argument 'size' should be a "
                                "non-negative integer (or long if Python 2).")
        elif src is not None:
            if isinstance(src, kaldi_vector.VectorBase):
                self.resize_(len(src), MatrixResizeType.UNDEFINED)
                self.CopyFromVec(src)
            elif isinstance(src, numpy.ndarray) and src.ndim == 1:
                self.resize_(len(src), MatrixResizeType.UNDEFINED)
                self.CopyFromVec(SubMatrix(src))
            else:
                raise TypeError("Vector argument 'src' should be a vector "
                                "or a 1-D numpy array.")

    def __getitem__(self, index):
        """Custom item indexing method.

        Returns:
            - the value at the given index if the index is an integer
            - a subvector if the index is a slice with step = 1
            - a list if the index is a slice with step > 1
        """
        if isinstance(index, int):
            return super(Vector, self).__getitem__(index)
        elif isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step == 1:
                return self.range(start, stop - start)
            return [self.__getitem__(i) for i in xrange(start, stop, step)]
        else:
            raise TypeError("Vector index must be an integer or a slice.")


class SubVector(kaldi_matrix_ext.SubVector, _VectorBase):
    """Python wrapper for kaldi::SubVector<float>"""

    def __init__(self, src, offset=0, length=None):
        """Creates a new subvector from the source (sub)vector.

        Subvector and the source vector (or numpy array) share the same
        underlying data storage. No data is copied.

        If 'length' is None, it defaults to len(src) - offset.

        Args:
            src (VectorBase): Source (sub)vector or 1-D numpy array.
            offset (int): Start of the subvector.
            length (int): Length of the subvector.
        """
        if not (isinstance(src, kaldi_vector.VectorBase) or
                isinstance(src, numpy.ndarray) and src.ndim == 1):
            raise TypeError("SubVector argument 'src' should be a vector "
                            "or a 1-D numpy array.")
        src_len = len(src)
        if not (0 <= offset <= src_len):
            raise IndexError("Argument offset={} should be in the range "
                             "[0,{}] when len(src)={}."
                             .format(offset, src_len, src_len))
        max_len = src_len - offset
        if length is None:
            length = max_len
        if not (0 <= length <= max_len):
            raise IndexError("Argument length={} should be in the range "
                             "[0,{}] when offset={} and len(src)={}."
                             .format(length, max_len, offset, src_len))
        super(SubVector, self).__init__(src, offset, length)

    def __getitem__(self, index):
        """Custom item indexing method.

        Returns:
            - the value at the given index if the index is an integer
            - a subvector if the index is a slice with step = 1
            - a list if the index is a slice with step > 1
        """
        if isinstance(index, int):
            return super(SubVector, self).__getitem__(index)
        elif isinstance(index, slice):
            start, stop, step = index.indices(len(self))
            if step == 1:
                return self.range(start, stop - start)
            return [self.__getitem__(i) for i in xrange(start, stop, step)]
        else:
            raise TypeError("SubVector index must be an integer or a slice.")


class _MatrixBase(object):
    def size(self):
        """Returns the size as a tuple (rows, cols)."""
        return self.num_rows_, self.num_cols_

    def nrows(self):
        """Returns the number of rows."""
        return self.num_rows_

    def ncols(self):
        """Returns the number of columns."""
        return self.num_cols_

    def equal(self, other, tol=1e-16):
        """Checks if matrices have the same size and data within tolerance."""
        return self.ApproxEqual(other, tol)

    def numpy(self):
        """Returns this matrix as a numpy ndarray."""
        return kaldi_matrix_ext.matrix_to_numpy(self)

    def range(self, row_offset, rows, col_offset, cols):
        """Returns a new submatrix of the matrix."""
        return SubMatrix(self, row_offset, rows, col_offset, cols)

    def __getitem__(self, index):
        """Custom indexing method

        Returns:
            - the value at the given index if the index is an integer tuple
            - a submatrix if both indices are slices with step = 1
            - a list if at least one index is a slice with step > 1
        """

        # Note (VM):
        # This allows for two brackets item access. 
        if isinstance(index, int):
            # Check if self is a matrix with row-dim or col-dim equals to 1
            
            # If so, we're asking a pseudo-vector to return a value
            if self.nrows() == 1:
                index = (0, index)
            
            elif self.ncols() == 1:
                index = (index, 0)
            
            # if not, we're actually asking for a row 
            else:
                index = (index, slice(0, self.ncols()))

        if isinstance(index, slice):
            
            # Is this a column pseudo-vector?
            if self.ncols() == 1:
                index = (index, 0)

            elif self.nrows() == 1:
                index = (0, index)
                
            else:
                index = (index, slice(0, self.ncols()))

        if isinstance(index, tuple):
            if len(index) != 2:
                raise IndexError("{} index must be a pair of integers or slices"
                                 .format(self.__class__.__name__))
            r, c = index

            # Simple indexing with two integers
            if isinstance(r, int) and isinstance(c, int):
                if r >= self.nrows() or c >= self.ncols():
                    raise IndexError("indices out of bounds.")

                if r < 0 or c < 0:
                    raise NotImplementedError("negative indices "
                                              "not implemented.")

                return self._getitem(r, c) #Call C-impl

            # Indexing with two slices
            elif isinstance(r, slice) and isinstance(c, slice):
                row_start, row_stop, row_step = r.indices(self.nrows())
                col_start, col_stop, col_step = c.indices(self.ncols())

                if row_step == 1 and col_step == 1:
                    rows, cols = row_stop - row_start, col_stop - col_start
                    return self.range(row_start, rows, col_start, cols)
                else:
                    return [[self._getitem(i, j)
                             for j in xrange(col_start, col_stop, col_step)
                            ] for i in xrange(row_start, row_stop, row_step)]

            # Row is a slice, Col is an int
            elif isinstance(r, slice) and isinstance(c, int):
                start, end, step = r.indices(self.nrows())
                if step == 1:
                    return self.range(start, end - start, c, 1)
                else:
                    return [self.__getitem__((i, c))
                            for i in xrange(start, end, step)]

            # Row is an int, Col is a slice
            elif isinstance(r, int) and isinstance(c, slice):
                start, end, step = c.indices(self.ncols())
                if step == 1:
                    return self.range(r, 1, start, end - start)
                else:
                    return [self.__getitem__((r, j))
                            for j in xrange(start, end, step)]

        raise TypeError("{} index must be an integer, slice, or tuple of integers or slices"
                        .format(self.__class__.__name__))

    def __setitem__(self, index, value):
        """Custom setitem method

        """
        if isinstance(index, tuple):
            if len(index) != 2:
                raise IndexError("{} index must be a pair of integers"
                                 .format(self.__class__.__name__))
            r, c = index
            if isinstance(r, int) and isinstance(c, int):
                if 0 <= r < self.nrows() and 0 <= c < self.ncols():
                    return self._setitem(r, c, value)

        raise TypeError("{} does not support given index type"
                         .format(self.__class__.__name__))

    def __repr__(self):
        return str(self)

    def __str__(self):
        # All strings are unicode in Python 3, while we have to encode unicode
        # strings in Python2. If we can't, let python decide the best
        # characters to replace unicode characters with.
        # Below implementation was taken from
        # https://github.com/pytorch/pytorch/blob/master/torch/tensor.py
        if sys.version_info > (3,):
            return _str._matrix_str(self)
        else:
            if hasattr(sys.stdout, 'encoding'):
                return _str._matrix_str(self).encode(
                    sys.stdout.encoding or 'UTF-8', 'replace')
            else:
                return _str._matrix_str(self).encode('UTF-8', 'replace')


class Matrix(kaldi_matrix.Matrix, _MatrixBase):
    """Python wrapper for kaldi::Matrix<float>"""
    def __init__(self, size=None, **kwargs):
        """Creates a new Matrix.

        If no arguments are given, returns a new empty matrix.
        If 'size' is given, returns a new matrix of given size.

        Args:
            size (tuple or list): Matrix dimensions (rows, cols)
        """
        super(Matrix, self).__init__()

        if size is not None:
            if not (isinstance(size, tuple) or isinstance(size, list)):
                raise TypeError("Matrix size argument must be a tuple or list.")

            if len(size) != 2:
                raise TypeError("Matrix size argument must be of length 2.")

            if not (isinstance(size[0], int) and isinstance(size[1], int)):
                raise TypeError("Matrix dimensions must be integer.")

            if not (size[0] > 0 and size[1] > 0):
                if not (size[0] == 0 and size[1] == 0):
                    raise TypeError("Both Matrix dimensions must be positive "
                                    "or both of them should be 0.")

            self.resize_(size[0], size[1], MatrixResizeType.UNDEFINED)

class SubMatrix(kaldi_matrix_ext.SubMatrix, _MatrixBase):
    def __init__(self, src, row_offset = 0, rows = None,
                            col_offset = 0, cols = None):
        """Creates a new submatrix from the source (sub)matrix.

           If 'rows' is None, it defaults to src.num_rows_ - row_offset.
           If 'cols' is None, it defaults to src.num_cols_ - col_offset.

           Args:
                src (MatrixBase): Source (sub)matrix or 2-D numpy array.
                row_offset, col_offset: Start of the submatrix.
                rows, cols: Dimensions of the submatrix.
        """
        if isinstance(src, kaldi_matrix.MatrixBase):
            src_rows, src_cols = src.num_rows_, src.num_cols_
        elif isinstance(src, numpy.ndarray) and src.ndim == 2:
            src_rows, src_cols = src.shape
        else:
            raise TypeError("SubMatrix argument 'src' should be a matrix "
                            "or a 2-D numpy array.")

        if not (0 <= row_offset <= src_rows):
            raise IndexError("Argument row_offset={} should be in the range "
                             "[0,{}] when src.num_rows_={}."
                             .format(row_offset, src_rows, src_rows))
        if not (0 <= col_offset <= src_cols):
            raise IndexError("Argument col_offset={} should be in the range "
                             "[0,{}] when src.num_cols_={}."
                             .format(col_offset, src_cols, src_cols))

        max_rows, max_cols = src_rows - row_offset, src_cols - col_offset
        if rows is None:
            rows = max_rows
        if cols is None:
            cols = max_cols

        if not (0 <= rows <= max_rows):
            raise IndexError("Argument rows={} should be in the range "
                             "[0,{}] when offset={} and src.num_rows_={}."
                             .format(rows, max_rows, row_offset, src_rows))
        if not (0 <= cols <= max_cols):
            raise IndexError("Argument cols={} should be in the range "
                             "[0,{}] when offset={} and src.num_cols_={}."
                             .format(cols, max_cols, col_offset, src_cols))

        super(SubMatrix, self).__init__(src, row_offset, rows, col_offset, cols)

################################################################################
# Define Vector and Matrix Utility Functions
################################################################################
