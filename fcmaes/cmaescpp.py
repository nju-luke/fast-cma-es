# Copyright (c) Dietmar Wolz.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory.

import sys
import os
import ctypes as ct
import numpy as np
from numpy.random import MT19937, Generator
from scipy.optimize import OptimizeResult
from fcmaes.cmaes import _check_bounds

os.environ['MKL_DEBUG_CPU_TYPE'] = '5'

def minimize(fun, 
             bounds=None, 
             x0=None, 
             input_sigma = 0.3, 
             popsize = 31, 
             max_evaluations = 100000, 
             max_iterations = 100000,  
             accuracy = 1.0, 
             stop_fittness = None, 
             is_terminate = None, 
             rg = Generator(MT19937()),
             runid=0):   
    """Minimization of a scalar function of one or more variables using a 
    C++ CMA-ES implementation called via ctypes.
     
    Parameters
    ----------
    fun : callable
        The objective function to be minimized.
            ``fun(x, *args) -> float``
        where ``x`` is an 1-D array with shape (n,) and ``args``
        is a tuple of the fixed parameters needed to completely
        specify the function.
    bounds : sequence or `Bounds`, optional
        Bounds on variables. There are two ways to specify the bounds:
            1. Instance of the `scipy.Bounds` class.
            2. Sequence of ``(min, max)`` pairs for each element in `x`. None
               is used to specify no bound.
    x0 : ndarray, shape (n,)
        Initial guess. Array of real elements of size (n,),
        where 'n' is the number of independent variables.  
    input_sigma : ndarray, shape (n,) or scalar
        Initial step size for each dimension.
    popsize = int, optional
        CMA-ES population size.
    max_evaluations : int, optional
        Forced termination after ``max_evaluations`` function evaluations.
    max_iterations : int, optional
        Forced termination after ``max_iterations`` iterations.
    accuracy : float, optional
        values > 1.0 reduce the accuracy.
    stop_fittness : float, optional 
         Limit for fitness value. If reached minimize terminates.
    is_terminate : callable, optional
        Callback to be used if the caller of minimize wants to 
        decide when to terminate. 
    rg = numpy.random.Generator, optional
        Random generator for creating random guesses.
    runid : int, optional
        id used by the is_terminate callback to identify the CMA-ES run. 
            
    Returns
    -------
    res : scipy.OptimizeResult
        The optimization result is represented as an ``OptimizeResult`` object.
        Important attributes are: ``x`` the solution array, 
        ``fun`` the best function value, ``nfev`` the number of function evaluations,
        ``nit`` the number of CMA-ES iterations, ``status`` the stopping critera and
        ``success`` a Boolean flag indicating if the optimizer exited successfully. """
    
    if not sys.platform.startswith('linux'):
        raise Exception("CMAES C++ variant currently only supported on Linux")
    lower, upper, guess = _check_bounds(bounds, x0, rg)   
    n = guess.size   
    if lower is None:
        lower = [0]*n
        upper = [0]*n
    mu = int(popsize/2)
    if np.ndim(input_sigma) == 0:
        input_sigma = [input_sigma] * n
    if stop_fittness is None:
        stop_fittness = np.nan   
    if is_terminate is None:    
        is_terminate=_is_terminate_false
        use_terminate = False 
    else:
        use_terminate = True 
    array_type = ct.c_double * n   
    c_callback = call_back_type(_c_func(fun))
    c_is_terminate = is_terminate_type(is_terminate)
    try:
        res = optimizeACMA_C(runid, c_callback, n, array_type(*guess), array_type(*lower), array_type(*upper), 
                           array_type(*input_sigma), max_iterations, max_evaluations, stop_fittness, mu, 
                           popsize, accuracy, use_terminate, c_is_terminate)
        x = np.array(np.fromiter(res, dtype=np.float64, count=n))
        val = res[n]
        evals = int(res[n+1])
        iterations = int(res[n+2])
        stop = int(res[n+3])
        freemem(res)
        return OptimizeResult(x=x, fun=val, nfev=evals, nit=iterations, status=stop, success=True)
    except Exception:
        return OptimizeResult(x=None, fun=sys.float_info.max, nfev=0, nit=0, status=-1, success=False)

def _is_terminate_false(runid, iterations, val):
    return False 

def _c_func(fun):
    """Convert an objective function for serial execution for cmaescpp.
    
    Parameters
    ----------
    fun : objective function mapping a list of float arguments to a float value

    Returns
    -------
    out : function
        A function suitable as ctypes based argument for cmaescpp.minimize."""
 
    return lambda n, x: fun([x[i] for i in range(n)])
  
if sys.platform.startswith('linux'):
    basepath = os.path.dirname(os.path.abspath(__file__))
    libcmalib = ct.cdll.LoadLibrary(basepath + '/lib/libacmalib.so')    
    call_back_type = ct.CFUNCTYPE(ct.c_double, ct.c_int, ct.POINTER(ct.c_double))  
    is_terminate_type = ct.CFUNCTYPE(ct.c_bool, ct.c_long, ct.c_int, ct.c_double)      
    optimizeACMA_C = libcmalib.optimizeACMA_C
    optimizeACMA_C.argtypes = [ct.c_long, call_back_type, ct.c_int, \
                ct.POINTER(ct.c_double), ct.POINTER(ct.c_double), ct.POINTER(ct.c_double), \
                ct.POINTER(ct.c_double), ct.c_int, ct.c_int, ct.c_double, ct.c_int, ct.c_int, \
                ct.c_double, ct.c_bool, is_terminate_type]
    
    optimizeACMA_C.restype = ct.POINTER(ct.c_double)         
    freemem = libcmalib.free_mem
    freemem.argtypes = [ct.POINTER(ct.c_double)]
    seed = libcmalib.seed
    seed.argtypes = [ct.c_int]
    seed_random = libcmalib.seedRandom
    seed_random.argtypes = []
 

