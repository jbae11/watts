# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

"""
This example demonstrates how to use WATTS to run an
GCMAT calculation. This example uses a nuclear
scenario.
"""

import watts
from pathlib import Path
import numpy as np
import time



params = watts.Parameters()


template_name = 'gcmat_template.txt'



final_demand_org = {'2025': 129942.80467537, '2026': 131242.232722123, '2027': 132554.655049345, '2028': 133880.201599838, '2029': 135219.003615836, '2030': 136571.193651995, '2031': 137936.905588515, '2032': 139316.2746444, '2033': 140709.437390844, '2034': 142116.531764752, '2035': 143537.6970824}
china_shares = {'2025': 0.1488, '2026': 0.1509, '2027': 0.153, '2028': 0.1551, '2029': 0.1572, '2030': 0.1593, '2031': 0.1614, '2032': 0.1635, '2033': 0.1656, '2034': 0.1677, '2035': 0.1698}
us_shares = {'2025': 0.167705168506287, '2026': 0.16583640931287, '2027': 0.164092357127913, '2028': 0.162454545105463, '2029': 0.160909323261296, '2030': 0.159448692009461, '2031': 0.158069206226392, '2032': 0.156774330726817, '2033': 0.155566621066295, '2034': 0.154449705570859, '2035': 0.153426207060785}
europe_shares = {'2025': 0.121418171095092, '2026': 0.119622503016436, '2027': 0.117931399291808, '2028': 0.116333503569193, '2029': 0.11482130552861, '2030': 0.113390051603732, '2031': 0.112036657179276, '2032': 0.110761596604602, '2033': 0.109563494760443, '2034': 0.108442445566371, '2035': 0.107398402556524}
row_shares = {'2025': 0.562076660398621, '2026': 0.563641087670695, '2027': 0.56497624358028, '2028': 0.566111951325344, '2029': 0.567069371210094, '2030': 0.567861256386808, '2031': 0.622751279451474, '2032': 0.625765072971703, '2033': 0.622194919609123, '2034': 0.622673325674434, '2035': 0.622981308570158}

#2025	2026	2027	2028	2029	2030	2031	2032	2033	2034	2035
#2.935E+07	2.921E+07	3.123E+07	3.134E+07	3.770E+07	3.991E+07	3.149E+07	3.611E+07	3.402E+07	3.372E+07	3.368E+07

us_new_demands = {'2025': 293500, '2026': 292100, '2027': 312300, '2028': 313400, '2029': 377000, '2030': 399100, '2031': 314900, '2032': 361100, '2033': 340200, '2034': 337200, '2035': 336800}
#from 2025 to 2035
# for i in range(2025, 2036):
# now only try 2025
for i in range(2025, 2026):
    china_demand = final_demand_org[str(i)] * china_shares[str(i)]
    us_demand = final_demand_org[str(i)] * us_shares[str(i)]
    europe_demand = final_demand_org[str(i)] * europe_shares[str(i)]
    row_demand = final_demand_org[str(i)] * row_shares[str(i)]
    us_new_demand = us_new_demands[str(i)]
    new_final_demand = china_demand  + europe_demand + row_demand + us_new_demand
    params[f'final_demand_{i}'] = new_final_demand
    params[f'china_{i}'] = china_demand/new_final_demand
    params[f'us_{i}'] = us_demand/new_final_demand
    params[f'eu_{i}'] = europe_demand/new_final_demand
    params[f'row_{i}'] = row_demand/new_final_demand

# params.show_summary(show_metadata=True, sort_by='key')
# accert_plugin = watts.PluginACCERT(input_name)
# accert_result = accert_plugin(params)
# gcmat_plugin = watts.PluginGCMAT('gcmat_template.txt', show_stdout=True, show_stderr=True)
# # run command is ./run_repast.sh $'1\tendAt\t2050' $(realpath .) testout
# gcmat_result = gcmat_plugin(params)



# Create a directory for storing results
results_path = Path.cwd() / 'results' 
results_path.mkdir(exist_ok=True, parents=True)

# Set the default path for the database
watts.Database.set_default_path(results_path)
print('results_path',results_path)
# Define some example parameter variations
end_years = [2040, 2050, 2060, 2070]
output_folders = [f"output_{year}" for year in end_years]

# Start timing the simulation
start = time.perf_counter()

# Loop through the variations and run the simulations
for end_year, output_folder in zip(end_years, output_folders):
    params['end_year'] = end_year
    params['output_folder'] = output_folder
    params['DATABASE_NAME'] = f'GCMAT_{end_year}.db'
    params.show_summary(show_metadata=True, sort_by='key')
    # Create the GCMAT plugin
    gcmat_plugin = watts.PluginGCMAT('gcmat_template.txt',show_stdout=False, show_stderr=True)
    
    # Run the simulation
    gcmat_result = gcmat_plugin(params, end_year=params['end_year'], output_folder=params['output_folder'])
    print('gcmat_result',gcmat_result.csv_data)

# End timing the simulation
end = time.perf_counter()

print(f'TOTAL SIMULATION TIME: {np.round((end - start) / 60, 2)} minutes')

