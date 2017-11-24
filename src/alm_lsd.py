import numpy as np
import numpy.linalg as la

from lsd_operations import dual_norm, shrink, min_cost_flow

import platform
project_float = np.float64 if '64' in platform.architecture()[0] else np.float32

def _calc_background_L(frames_D, dual_Y, dual_mu, foreground_S):
    background_G_L = frames_D - foreground_S + dual_Y / dual_mu
    return shrink(background_G_L, 1.0 / dual_mu)

def _calc_foreground_S(frames_D, dual_Y, dual_mu, background_L, graph, regularization_lambda):
    foreground_G_S = frames_D - background_L + dual_Y / dual_mu
    return min_cost_flow(foreground_G_S, graph, regularization_lambda / dual_mu)

def _calc_Y(frames_D, dual_Y, dual_mu, background_L, foreground_S):
    return dual_Y + dual_mu * (frames_D - background_L - foreground_S)

def _calc_error(frames_D, background_L, foreground_S):
    distance = frames_D - background_L - foreground_S
    return la.norm(distance,'fro') / la.norm(frames_D,'fro');

def inexact_alm_lsd(frames_D, graph, max_iterations=100):
    alm_penalty_scalar_rho = 1.5
    tolerance = 1e-7
    err = []
    num_pixels_n, num_frames_p = frames_D.shape
    regularization_lambda = 1.0 / np.sqrt(num_pixels_n)
    dual_mu = 12.5 / la.norm(frames_D, ord=2)
    dual_Y = frames_D / dual_norm(frames_D, regularization_lambda)
    foreground_S = np.zeros_like(frames_D) # E in reference code
    background_L = np.zeros_like(frames_D) # A in reference code
    for t in range(max_iterations):
        background_L = _calc_background_L(frames_D, dual_Y, dual_mu, foreground_S)
        foreground_S = _calc_foreground_S(frames_D, dual_Y, dual_mu, background_L, graph, regularization_lambda)
        dual_Y = _calc_Y(frames_D, dual_Y, dual_mu, background_L, foreground_S)
        dual_mu = alm_penalty_scalar_rho * dual_mu
        err.append(_calc_error(frames_D, background_L, foreground_S))
        # if err[-1] < tolerance:
        if len(err) > 100:
            break
    return background_L, foreground_S, err


# block spase RPCA
def _calc_foreground_S_bs(frames_D, dual_Y, dual_mu, background_L, group_info):
    G = frames_D - background_L + dual_Y / dual_mu
    ret_S = np.zeros_like(G)
    for i in range(len(group_info)):
        loc = group_info[i]['indexes']
        thresh = group_info[i]['lambda'] / dual_mu
        
        val = la.norm(G[loc], ord=2)
            
        coeff = 0;
        if(val > thresh): coeff = (val - thresh)/val;
        ret_S[loc] = coeff * G[loc]
        
    return ret_S

def inexact_alm_bs(frames_D, group_info, max_iterations=100):
    alm_penalty_scalar_rho = 1.5
    tolerance = 1e-7
    err = []    
    num_pixels_n, num_frames_p = frames_D.shape
    ref_lambda = 0.1 / max(num_pixels_n, num_frames_p)
    mu0 = 1.25 / la.norm(frames_D, ord=2)
    def J(M):
        return max(la.norm(M, ord=2), la.norm(M, ord='inf')/ref_lambda)
    
    dual_mu = mu0
    dual_Y = frames_D / J(frames_D)
    foreground_S = np.zeros_like(frames_D) # E in reference code
    background_L = np.zeros_like(frames_D) # A in reference code
    
    for t in range(max_iterations):
        background_L = _calc_background_L(frames_D, dual_Y, dual_mu, foreground_S)
        foreground_S = _calc_foreground_S_bs(frames_D, dual_Y, dual_mu, background_L, group_info)
        dual_Y = _calc_Y(frames_D, dual_Y, dual_mu, background_L, foreground_S)
        dual_mu = min(alm_penalty_scalar_rho * dual_mu, tolerance * mu0)
        err.append(_calc_error(frames_D, background_L, foreground_S))
        if err[-1] < tolerance:
            break
    return background_L, foreground_S, err
