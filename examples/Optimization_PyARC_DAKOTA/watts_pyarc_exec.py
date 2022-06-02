# SPDX-FileCopyrightText: 2022 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use DAKOTA to perform 
optimization of a WATTS workflow. 
"""
import shutil
import watts
from astropy.units import Quantity

# TH params
params = watts.Parameters()

input_file = open("input.txt", "r").readlines() 
for l in range(len(input_file)):
    if "assembly_pitch" in input_file[l]: params['assembly_pitch'] = Quantity(float(input_file[l].split()[-1]), "cm")  
    if "assembly_length" in input_file[l]: params['assembly_length'] = Quantity(float(input_file[l].split()[-1]), "cm")

params['temp'] = Quantity({{ temp }}, "Celsius")  # 300 K

# PyARC Workflow
pyarc_plugin = watts.PluginPyARC('pyarc_template', show_stdout=True, extra_inputs=['lumped.son', 'pyarc_input.isotxs']) # show all the output
pyarc_result = pyarc_plugin(params)
params['keff-dif3d'] = pyarc_result.results_data["keff_dif3d"][0.0]
params['core_weight'] = pyarc_result.results_data["rebus_inventory"][0][('CORE', 'TOTAL')]

# Generate output file for Dakota driver
for p in pyarc_result.inputs:
    if "pyarc_input.son" in str(p):
        shutil.copyfile(str(p), "pyarc_input.son")
for p in pyarc_result.outputs:
    if "pyarc_input.summary" in str(p):
        shutil.copyfile(str(p), "pyarc_input.summary")
    if "pyarc_input.out" in str(p):
        shutil.copyfile(str(p), "pyarc_input.out")

# The output file MUST be named as "opt_res.out" for the Dakota plugin to extract the values.
# Given that the Dakota plugin essentially reads a text file, it is up to the user to ensure that
# the order of the items matches that in the Dakota input file. The format of each row is trivial
# as long as the values of the parameters are provided in a row-wise fashion, i.e. only one value
# per row.
results_opt = open("opt_res.out", "w")
results_opt.writelines("\nKeffOpt = %8.3f "%(params['keff-dif3d']))
results_opt.writelines("\nCoreWeight = %8.3f "%(params['core_weight']))
results_opt.writelines("\nKeffCrit = %8.3f "%(params['keff-dif3d']))
results_opt.close()
print(f"results: KeffOpt = {params['keff-dif3d']} - HNinventory = {params['core_weight']} ")
