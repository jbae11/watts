# SPDX-FileCopyrightText: 2022-2023 UChicago Argonne, LLC
# SPDX-License-Identifier: MIT

from functools import lru_cache
from pathlib import Path
from typing import Callable, Mapping, List, Optional

from uncertainties import ufloat

import sqlite3 as lite
import numpy as np
import os

from .fileutils import PathLike
from .parameters import Parameters
from .plugin import Plugin, PluginGeneric, _find_executable
from .results import Results, ExecInfo

class ResultsCyclus(Results):
    """Cyclus simulation restuls

    Parameters
    ----------
    params
        Parameters used to generate inputs
    exec_info
        Execution information (job ID, plugin name, timestamp, etc.)
    inputs
        List of input files
    outputs
        List of output files

    Attributes
    ----------
    keff
        K-effective value from the final statepoint
    statepoints
        List of statepoint files
    """

    def __init__(self, params: Parameters, exec_info: ExecInfo,
                 inputs: List[Path], outputs: List[Path]):
        super().__init__(params, exec_info, inputs, outputs)
        #! can't do this because sqlite cursors can't be pickled
        # self.obj = CyclusOutput(self.sqlite_file)

    @property
    def sqlite_file(self) -> Path:
        l = [p for p in self.outputs if p.name.endswith('sqlite')]
        assert(len(l) == 1)
        return l[0]

    @property
    def commodities(self) -> List[str]:
        obj = CyclusOutput(self.sqlite_file)
        q = obj.cur.execute('SELECT distinct(commodity) FROM transactions').fetchall()
        return [x['commodity'] for x in q]

    @property
    def time_dict(self) -> dict:
        obj = CyclusOutput(self.sqlite_file)
        return obj.get_times()
    
    @property
    def mass_flow_dict(self) -> dict:
        obj = CyclusOutput(self.sqlite_file)
        arr = obj.get_fuel_demands(self.commodities)
        d = {}
        for indx in range(len(arr)):
            d[self.commodities[indx]] = arr[indx,:]
        return d



class PluginCyclus(PluginGeneric):
    """Plugin for running Cyclus

    #! In addition to the basic capability to use placeholders in MCNP input files,
    this class also provides a custom Jinja filter called ``expand_element``
    that allows you to specify natural elements in MCNP material definitions and
    have them automatically expanded based on what isotopes appear in the xsdir
    file.

    Parameters
    ----------
    template_file
        Templated Cyclus input (.xml)
    executable
        Path to Cyclus executable
    show_stdout
        Whether to display output from stdout when Cyclus is run
    show_stderr
        Whether to display output from stderr when Cyclus is run

    Attributes
    ----------
    executable
        Path to Cyclu executable
    execute_command
        List of command-line arguments used to call the executable

    """

    def __init__(
        self,
        template_file: str,
        executable: PathLike = 'cyclus',
        show_stdout: bool = False,
        show_stderr: bool = False
    ):
        executable = _find_executable(executable, 'PATH')
        output_name = template_file.replace('.xml', '.sqlite')
        super().__init__(
            executable, ['{self.executable}', '{self.input_name}', '-o', output_name],
            # executable, [self.executable, template_file, '-o', output_name],
            template_file, plugin_name="Cyclus",
            show_stdout=show_stdout,
            show_stderr=show_stderr,
            unit_system='si')
        self.input_name = "cyclus_input"
    

class CyclusOutput:
    def __init__(self, path):
        '''
        Class to access and browse an output file from Cyclus.
        Output file MUST be an SQLite database (.sqlite)
        Parameters:
        -----------
        path: str 
            path to output file, including file name
        '''
        assert(os.path.exists(path)), 'File does not exist.'
        ext = os.path.splitext(path)
        assert(ext[-1] == '.sqlite'), 'File extension has to be .sqlite'
        con = lite.connect(path)
        con.row_factory = lite.Row
        self.cur = con.cursor()
        # get times
        td = self.get_times()
        for k,v in td.items():
            setattr(self, k, v)

    
    def get_times(self):
        '''
        Gets different time-related data from a simulation

        Parameters:
        -----------

        Returns:
        --------
        dict
            {'init_year':int, 'init_month':int,
             'duration':int, 'time': int, 'years':int}
        '''
        q = self.cur.execute('SELECT prototype, entertime, lifetime, Spec, value FROM agententry INNER JOIN timeseriespower ON agententry.agentid = timeseriespower.agentid WHERE agententry.spec LIKE "%Reactor" AND value != 0 GROUP BY agententry.agentid').fetchall()
        duration = self.cur.execute('SELECT InitialYear, InitialMonth, Duration FROM Info').fetchone()
        init_year = duration['InitialYear']
        init_month = duration['InitialMonth']
        duration = duration['Duration']
        time = init_year + (np.arange(duration)+init_month-1)/12
        years = time
        return {'init_year': init_year, 'init_month': init_month,
                'duration': duration, 'years': years}


    def get_deployment_dict(self, reactors, misc_key='legacy'):
        '''
        Determines the amount of deployed power for each time step for 
        each reactor prototype

        Parameters:
        -----------
        reactors: list of str
            names of reactor prototypes in the simulation
        misc_key: str
            prototype name to skip over in database
        
        Returns:
        --------
        power_dict: dictionary
            keys are strings, the reactor names and 'legacy',
            the values are a numpy array with one element for 
            each time step in the scenario, indicating how 
            much power is deployed for each key during the 
            smulation.
        '''
        q = self.cur.execute('SELECT prototype, entertime, lifetime, Spec, value FROM agententry INNER JOIN timeseriespower ON agententry.agentid = timeseriespower.agentid WHERE agententry.spec LIKE "%Reactor" AND value != 0 GROUP BY agententry.agentid').fetchall()

        power = np.zeros(self.duration)

        power_dict = {k:np.zeros(self.duration) for k in reactors}
        power_dict['legacy'] = np.zeros(self.duration)
        pow_cap_dict = {k:0 for k in reactors if k != misc_key}
        
        for row in q:
            proto = row['prototype']
            t0 = row['entertime']
            t1 = row['lifetime']

            found = False
            for react_ in reactors:
                if react_ in proto:
                    key = react_
                    found = True
                    if react_ == proto:
                        pow_cap_dict[react_] = row['value'] * 1e-3
            if not found:
                key = misc_key
              
            power_dict[key][t0-1:t0+t1-1] += row['value'] * 1e-3
        return power_dict
    

    def get_fuel_demands(self, fuel_forms):
        '''
        
        Parameters:
        -----------
        fuel_forms: list of strs
            name of the different commodities for reactor fuel

        Returns:
        --------
        fuel_flow_array: 2D numpy array
            each row (axis 0) corresponds to a fuel form in the 
            fuel_forms list (index in fuel_forms corresponds to 
            the 0 axis location in fuel_flow_array), the columns 
            (axis 1) correspond to each year of the simulation,
            with the data being the yearly totals of 
            each fuel form
        '''
        l_ = len(self.get_yearly_sum(np.zeros(self.duration)))
        fuel_flow_array = np.zeros((len(fuel_forms), l_))
        for indx, ff in enumerate(fuel_forms):
            query = self.cur.execute('''SELECT sum(quantity), time FROM transactions INNER JOIN resources
                        ON transactions.resourceid = resources.resourceid WHERE Commodity="%s"
                        GROUP BY time''' %ff).fetchall()
            fuel_flow_array[indx, :] = np.array(self.get_yearly_sum(self.query_to_array(query, self.duration, 'time', 'sum(quantity)')))
        return fuel_flow_array


    @staticmethod
    def query_to_array(query_result, duration, time_label='entertime', value_label=''):
        '''
        Transform the results from a specified data query of the SQLite 
        into a numpy array.
        Parameters:
        -----------
        query_result: list 
            SQLite query for database
        duration: int 
            number of time steps
        time_label: str
            name of column to indicate time in the table
            default = 'entertime'
        value_label: str
            how to treat the values of interest, default = '',
            potential input is 'sum(quantity)'
        '''
        val = np.zeros(duration)
        for row in query_result:
            if not value_label:
                val[row[time_label]] += 1
            else:
                val[row[time_label]] += row[value_label]
        return np.array(val)

    @staticmethod
    def get_yearly_sum(arr):
        '''
        Parameters:
        -----------
        arr: numpy array
            1D array of length that typically corresponds to the number 
            of time steps in a simulation, with data for each time step.

        Returns:
        --------
        newarr: numpy array
            length is the number of years in a simulations (i.e., 
            length of arr/12) with the data from arr summed up for each 
            year 
        '''
        newarr = []
        c = 0
        for indx, val in enumerate(arr):
            if indx%12 == 0:
                newarr.append(c)
                c = 0
            c += val
        return np.array(newarr[:])

