"""Shared parsing of simulation filenames into physics metadata.

This module intentionally contains no Qt or application-controller dependencies.
Filename grammar is treated as a compatibility/data-schema contract.
"""

import os
import re
from typing import Tuple


def parse_filename_parameters(filename: str) -> dict:
    """Extracts physical parameters from standard filename conventions as fallback."""
    params = {}
    base = os.path.splitext(os.path.basename(filename))[0]

    mu_m = re.search(r"mu[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if mu_m:
        try: params["mu"] = float(mu_m.group(1))
        except ValueError: pass

    t_m = re.search(r"(?:^|[^0-9a-zA-Z])t[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if t_m:
        try: params["t"] = float(t_m.group(1))
        except ValueError: pass

    t1_m = re.search(r"t1[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if t1_m:
        try: params["t1"] = float(t1_m.group(1))
        except ValueError: pass

    k_m = re.search(r"(?:^|[^0-9a-zA-Z])K[_=]?([0-9]+(?:\.[0-9]+)?)", base)
    if k_m:
        try: params["K"] = float(k_m.group(1))
        except ValueError: pass

    n_m = re.search(r"(?:^|[^0-9a-zA-Z])N[_=]?(\d+)", base)
    if n_m:
        try: params["N"] = int(n_m.group(1))
        except ValueError: pass

    nw_m = re.search(r"(?:Nw|num_omega|w)[_=]?(\d+)", base, re.IGNORECASE)
    if nw_m:
        try: params["num_omega"] = int(nw_m.group(1))
        except ValueError: pass

    eta_m = re.search(r"eta[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if eta_m:
        try: params["eta"] = float(eta_m.group(1))
        except ValueError: pass

    jp_m = re.search(r"(?:J_perp|Jperp|fixed_J)[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
    if jp_m:
        try:
            val = float(jp_m.group(1))
            params["fixed_jperp"] = val
            params["jperp"] = val
        except ValueError: pass

    # Multi-value or single JK
    jk_vals_m = re.search(r"(?:J_K|JK)_vals_([0-9._]+)", base, re.IGNORECASE)
    if jk_vals_m:
        raw = jk_vals_m.group(1).split('_Jperp')[0]
        vals = []
        for v in raw.split('_'):
            try: vals.append(float(v))
            except ValueError: pass
        if vals:
            params["jk"] = vals
            params["fixed_jk"] = vals[0]
    else:
        jk_m = re.search(r"(?:J_K|JK|fixed_JK)[_=]?([0-9]+(?:\.[0-9]+)?)", base, re.IGNORECASE)
        if jk_m:
            try:
                val = float(jk_m.group(1))
                params["fixed_jk"] = val
                params["jk"] = [val]
            except ValueError: pass

    return params



def parse_plot_metadata(filepath: str) -> Tuple[str, str, str, str, str]:
    """
    Parses a simulation plot filepath into clean, human-readable physics metadata.
    Returns: (title, params_str, category_tag, observable_type, raw_filename)
    """
    fname = os.path.basename(filepath)
    stem = os.path.splitext(fname)[0]

    # 1. Susceptibility Sweep: sweep_JK_fixed_J_6.0_mu_1.00_dynamic.png or sweep_J_fixed_JK_6.0_mu_1.00_dynamic.png
    m_susc = re.search(r'sweep_(JK|J_perp|Jperp|J)_fixed_(?:J|JK|J_perp|Jperp)_*([0-9.]+)_*mu_*([0-9.-]+)_*([a-zA-Z]+)', stem, re.IGNORECASE)
    if m_susc:
        mode, fixed_val, mu, kind = m_susc.groups()
        fixed_name = 'J_⊥' if mode.upper() in ('JK', 'J_K') else 'J_K'
        sweep_name = 'J_K Sweep' if mode.upper() in ('JK', 'J_K') else 'J_⊥ Sweep'
        is_dyn = kind.lower() == 'dynamic'
        kind_title = 'Dynamic Susceptibility χ(q, ω)' if is_dyn else 'Static Susceptibility χ(q, 0)'
        obs_type = 'Dynamic Susceptibility χ(q, ω)' if is_dyn else 'Static Susceptibility χ(q, 0)'
        params = [sweep_name, f'{fixed_name} = {fixed_val}', f'μ = {mu}']
        return kind_title, '  •  '.join(params), '🧲 Susceptibility', obs_type, fname

    # 2. Magnetic Phase Diagram: phase_diagram_mu1.00_AFM.png
    m_phase = re.search(r'phase_diagram_mu_*([0-9.-]+)_*([A-Z]+)', stem, re.IGNORECASE)
    if m_phase:
        mu, k_type = m_phase.groups()
        k_desc = 'K > 0 (AFM)' if k_type.upper() == 'AFM' else 'K < 0 (FM)'
        title = f'Magnetic Phase Diagram ({k_type.upper()})'
        params = [k_desc, f'μ = {mu}']
        return title, '  •  '.join(params), '🧲 Susceptibility', 'Magnetic Phase Diagram', fname

    # 3. Quasiparticle Spectral Function: both_JK_fixed_Jperp6.00_k_0.5_0.5_mu1.00.png or both_JK_k_1_0_mu_1.0.png
    m_spec = re.search(r'(both|spectral|self_energy)_(JK|Jperp)_*(?:fixed_)?(?:Jperp|JK)?_*([0-9.]*)_k_([0-9.]+)_([0-9.]+)_mu_*([0-9.-]+)', stem, re.IGNORECASE)
    if m_spec:
        obs, sweep_m, fixed_val, kx, ky, mu = m_spec.groups()
        obs_map = {
            'both': 'Quasiparticle Spectral A(k, ω) & Self-Energy',
            'spectral': 'Quasiparticle Spectral A(k, ω)',
            'self_energy': 'Self-Energy Re Σ & Im Σ'
        }
        title = obs_map.get(obs.lower(), 'Spectral Analysis')
        sweep_name = 'J_K Sweep' if 'JK' in sweep_m.upper() else 'J_⊥ Sweep'
        fixed_val_str = fixed_val if fixed_val else '6.0'
        fixed_name = 'J_⊥' if 'JK' in sweep_m.upper() else 'J_K'
        k_str = f'k = ({kx}π, {ky}π)' if ky != '0' else f'k = ({kx}π, 0)'
        if kx == '0' and ky == '0':
            k_str = 'k = (0, 0)'
        params = [sweep_name, f'{fixed_name} = {fixed_val_str}', k_str, f'μ = {mu}']
        return title, '  •  '.join(params), '🌊 Spectral', 'Quasiparticle Spectral A(k, ω)', fname

    # 4. Spectral Sweep Subplots: sweep_DOS_atJ_perp_6.0_mu_1.0.png or sweep_FS_... or sweep_Path_...
    m_se = re.search(r'sweep_(DOS|FS|Path)_at_*(J_perp|J_K|Jperp|JK)_*([0-9.]+)_*mu_*([0-9.-]+)', stem, re.IGNORECASE)
    if m_se:
        ptype, fixed_m, fixed_val, mu = m_se.groups()
        type_map = {
            'DOS': ('Density of States (DOS)', 'Density of States (DOS)'),
            'FS': ('Fermi Surface (FS)', 'Fermi Surface (FS)'),
            'PATH': ('Band Dispersion along High-Symmetry Path', 'Band Dispersion (Path)')
        }
        title, obs_type = type_map.get(ptype.upper(), (ptype, 'Spectral'))
        sweep_name = 'J_K Sweep' if 'perp' in fixed_m.lower() else 'J_⊥ Sweep'
        fixed_name = 'J_⊥' if 'perp' in fixed_m.lower() else 'J_K'
        params = [sweep_name, f'{fixed_name} = {fixed_val}', f'μ = {mu}']
        return title, '  •  '.join(params), '🌊 Spectral', obs_type, fname

    # 5. Conductivity plots and sweeps: conductivity_JK_... or sweep_conductivity_...
    if stem.lower().startswith('sweep_conductivity_') or stem.lower().startswith('conductivity_'):
        is_sweep = stem.lower().startswith('sweep_conductivity_')
        title = 'Electrical Conductivity Sweep' if is_sweep else 'Electrical Conductivity σ(ω)'
        obs_type = 'Electrical Conductivity σ(ω)'
        cat = '⚡ Conductivity'
        params = []
        jk_m = re.search(r'JK_([0-9.]+)', stem)
        if jk_m: params.append(f'J_K = {jk_m.group(1)}')
        jp_m = re.search(r'Jperp_([0-9.]+)', stem) or re.search(r'J_perp_([0-9.]+)', stem)
        if jp_m: params.append(f'J_⊥ = {jp_m.group(1)}')
        mu_m = re.search(r'mu_([0-9.-]+)', stem)
        if mu_m: params.append(f'μ = {mu_m.group(1)}')
        if is_sweep:
            mode_m = 'J_K Sweep' if 'vals' in stem and 'jk' in stem.lower() else 'J_⊥ Sweep'
            params.insert(0, mode_m)
        return title, '  •  '.join(params), cat, obs_type, fname

    # 6. Composite sweeps: sweep_JK_vals_3.00_6.00_9.00_Jperp_6.00...png
    if 'sweep_jk' in stem.lower() or 'sweep_jperp' in stem.lower():
        title = 'Spectral Sweep Suite [DOS, FS, Path]'
        params = []
        jp_m = re.search(r'Jperp_([0-9.]+)', stem)
        if jp_m: params.append(f'J_⊥ = {jp_m.group(1)}')
        mu_m = re.search(r'mu_([0-9.-]+)', stem)
        if mu_m: params.append(f'μ = {mu_m.group(1)}')
        n_m = re.search(r'N_([0-9]+)', stem)
        if n_m: params.append(f'N = {n_m.group(1)}')
        return title, '  •  '.join(params) if params else 'Multi-Coupling Sweep', '🌊 Spectral', 'Band Dispersion (Path)', fname

    # Fallback
    clean_title = stem.replace('_', ' ').replace('-', ' ').title()
    cat = '🧲 Susceptibility' if any(k in filepath.lower() for k in ('susc', 'chi', 'phase')) else '🌊 Spectral'
    obs_type = 'Other Observable'
    return clean_title, '', cat, obs_type, fname
