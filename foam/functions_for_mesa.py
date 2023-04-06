"""A few helpful functions to process MESA output."""
# from foam import functions_for_mesa as ffm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import multiprocessing, glob, h5py
from pathlib import Path
from functools import partial
from foam import support_functions as sf

################################################################################
def read_mesa_file(file_path, index_col=None):
    """
    Read in a mesa profile or history file and return 2 dictionaries.
    The first with the header info, and the second with the data.
    If the format is hdf5, assumes the attributes are the MESA header.
    If the format is not an hdf5 file, assumes the default MESA output format.
    This format is an ascii file delimited by whitespace with the following structure:
    line 1: header names
    line 2: header data
    line 3: blank
    line 4: main data names
    line >4:main data values

    ------- Parameters -------
    file_path: String
        The path to the MESA profile or history file to read in.
    ------- Returns -------
    header: dictionary
        A dictionary holding the header info of the MESA file.
    data: dictionary
        A dictionary holding the data columns of the MESA file as numpy arrays.
    """
    if h5py.is_hdf5(file_path):
        return sf.read_hdf5(file_path)

    else:   # assumes the default MESA output format
        header_df = pd.read_table(file_path, delim_whitespace=True, nrows=1, header=1)
        data_df = pd.read_table(file_path, delim_whitespace=True, skiprows=3, header=1, index_col=index_col)

        header={}
        for k in header_df.keys():
            header.update({k: header_df[k].to_numpy()[0]})
        data = {}
        for k in data_df.keys():
            data.update({k: data_df[k].to_numpy()})

        return header, data

################################################################################
def check_hydro_eq(profile_file, treshold_for_plot=5E-8):
    """
    Calculates the normalised differences between the terms on both sides of the hydrostatic equilibrium equation.
    Makes a plot if the values exceed a given treshold.
    This shows how well hydrostatic equilibrium has been fulfilled in the MESA model.
    ------- Parameters -------
    profile_file: String
        The path to the profile file to be checked.
    treshold_for_plot: float
        Make a plot if the max difference between the left and right hand side of the equation is greater than this number.
    """
    header, data = read_mesa_file(profile_file)
    # Compute the hydrostatic equilibrium quality factor q - See e.g. Aerts et al. (2010)
    lhs=np.delete(data['hyeq_lhs'], 0)  # remove the values at the surface, since these are 0
    rhs=np.delete(data['hyeq_rhs'], 0)

    norm = np.max(np.vstack([lhs, rhs]), axis=0)
    hyeq = np.abs(lhs - rhs) / np.abs(norm)

    # Make the plot if the treshold criterion is met
    if max(hyeq) > treshold_for_plot:
        # print the maximal deviation and profile name
        print(max(hyeq))
        print(profile_file)
        # make a semilog plot
        fig=plt.figure()
        ax = fig.add_subplot(111)
        ax.semilogy(np.delete(data['radius'], 0), hyeq, 'ko-') #also remove surface value, to have same amount of datapoints
        plt.show()
        plt.clf()
        plt.close('all')

################################################################################
def plot_MESA_file(profile_file, x_value, y_value, ax=None, label_size=16, colour='', linestyle='solid', alpha=1, legend=True, label=None):
    """
    Plot the requested quantities for the given MESA profile or history file.
    ------- Parameters -------
    profile_file: String
        The path to the profile file to be used for the plotting.
    x_value, y_value,: String
        The parameters of the profile plotted on the x and y axis.
        If x_value is mass or radius, it will be put in units relative to the total mass or radius
    ax: an axis object
        Axes object on which the plot will be made. If None: make figure and axis within this function.
    label_size, alpha: float
        The size of the labels in the figure, and transparency of the plot
    colour, linestyle, label: float
        Settings for the plot
    legend: boolean
        Flag to enable or disable a legend on the figure
    """
    if ax is None:
        fig=plt.figure()
        ax = fig.add_subplot(111)

    header, data = read_mesa_file(profile_file)
    # from "data", extract the columns
    y   = np.asarray(data[y_value])
    x   = np.asarray(data[x_value])
    if label == None:   #Set the label to be the name of the y variable
        label = y_value
    if x_value == 'radius' or x_value == 'mass':
        x = x/x[0] # normalized radius/mass coordinates
        ax.set_xlim(0,1)
    # generate the plot, in which colour will not be specified
    if colour == '':
        ax.plot( x , y, label=label, linestyle=linestyle, alpha=alpha)
    # generate the plot, in which colour will be specified
    else:
        ax.plot( x , y, label=label, linestyle=linestyle, alpha=alpha, color=colour)
    if legend is True:
        ax.legend(loc='best', prop={'size': label_size})
    ax.set_xlabel(x_value, size=label_size)
    ax.set_ylabel(y_value, size=label_size)

################################################################################
def mesh_histogram(profile_file, x_value='radius', ax=None, label_size=16, colour='', linestyle='solid', alpha=1, legend=True, label=None, bins=200):
    """
    Make a histogram of the mesh points in the MESA profile
    ------- Parameters -------
    profile_file: String
        The path to the profile file to be used for the plotting.
    x_value: String
        The x value to use for the histogram
        If x_value is mass or radius, it will be put in units relative to the total mass or radius
    ax: an axis object
        Axes object on which the plot will be made. If None: make figure and axis within this function.
    label_size, alpha: float
        The size of the labels in the figure, and transparency of the plot
    colour, linestyle, label: float
        Settings for the plot
    legend: boolean
        Flag to enable or disable a legend on the figure.
    bins: int
        Number of bins used in the histogram
    """
    if ax is None:
        fig=plt.figure()
        ax = fig.add_subplot(111)

    header, data = read_mesa_file(profile_file)
    print(f'Total zones of {profile_file} : {header["num_zones"]}')

    # from "data", extract the columns
    x   = np.asarray(data[x_value])
    if label == None:   #Set the label to be the name of the y variable
        legend = False
    if x_value == 'radius' or x_value == 'mass':
        x = x/x[0] # normalized radius/mass coordinates
        ax.set_xlim(0,1)
    # generate the plot, in which colour will not be specified
    if colour == '':
        ax.hist(x, bins=bins, histtype=u'step', label=label, alpha=alpha, linestyle=linestyle)
    # generate the plot, in which colour will be specified
    else:
        ax.hist(x, bins=bins, histtype=u'step', label=label, alpha=alpha, linestyle=linestyle, color=colour)
    # generate a legend if true
    if legend is True:
        ax.legend(loc='best', prop={'size': label_size})
    ax.set_xlabel(x_value, size=label_size)
    ax.set_ylabel('Meshpoints', size=label_size)

################################################################################
def plot_HRD(hist_file, ax=None, colour='blue', linestyle='solid', label='', label_size=16,
    Xc_marked=None, Teff_logscale=True, start_track_from_Xc=None, diagram='HRD'):
    """
    Makes an HRD plot from a provided history file
    ------- Parameters -------
    hist_file: String
        The path to the profile file to be used for the plot.
    ax: an axis object
        Axes object on which the plot will be made. If None: make figure and axis within this function.
    colour, linestyle, label: strings
        Specify the colour, linestyle and label of the plotted data.
    label_size: float
        The size of the labels in the figure.
    Xc_marked: list of floats
        Models with these Xc values are marked with red dots on the plot (listed in increasing value).
    Teff_logscale: boolean
        Plot effective temperature in logscale (True), or not (False).
    start_track_from_Xc: float
        Only start plotting the track if Xc drops below this value (e.g. to not plot the initial relaxation loop).
    diagram: string
        Type of diagram that is plotted. Options are HRD (logL vs logTeff), sHRD (log(Teff^4/g) vs logTeff) or kiel (logg vs logTeff).
    """
    if ax is None:
        fig = plt.figure()
        ax = fig.add_subplot(111)

    header, data = read_mesa_file(hist_file)

    # From "data", extract the required columns as numpy arrays
    log_L     = np.asarray(data['log_L'])
    log_Teff  = np.asarray(data['log_Teff'])
    log_g     = np.asarray(data['log_g'])
    center_h1 = np.asarray(data['center_h1'])

    # Plot the x-axis in log scale
    if Teff_logscale:
        T = log_Teff
        ax.set_xlabel(r'log(T$_{\mathrm{eff}}$)', size=label_size)
    # Plot the x-axis in linear scale
    else:
        T = 10**log_Teff
        ax.set_xlabel(r'T$_{\mathrm{eff}}$ [K]', size=label_size)

    # Plot HRD
    if diagram == 'HRD':
        y_axis = log_L
        ax.set_ylabel(r'log(L/L$_{\odot}$)', size=label_size)
    # Plot sHRD (log_Teff^4/log_g vs log_Teff)
    elif diagram == 'sHRD':
        log_Lsun = 10.61
        y_axis = 4*log_Teff - log_g - log_Lsun
        ax.set_ylabel(r'$\log \left(\frac{{T_{\mathrm{eff}}}^4}{g}\right) \ (\mathscr{L}_\odot)$', size=label_size)
    # Plot Kiel diagram (log_g vs log_Teff)
    elif diagram == 'kiel':
        y_axis = log_g
        ax.set_ylabel(r'log g [dex]', size=label_size)

    # Start plotting from Xc value
    if start_track_from_Xc!= None:
        for i in range(len(center_h1)):
            if center_h1[i] < start_track_from_Xc:
                T = T[i:]
                y_axis = y_axis[i:]
                break

    # Plot the HRD diagram (log_L vs. T)
    ax.plot(T, y_axis, color = colour, linestyle = linestyle, label = label)

    # Put specific marks on the HRD diagram
    if Xc_marked is None:
        return
    k = 0
    for i in range(len(center_h1)-1, -1, -1):
        if center_h1[i] > Xc_marked[k]:
            ax.scatter( T[i] , log_L[i], marker='o', color = 'red', lw=2)
            k += 1
            if k >= len(Xc_marked):
                return

################################################################################
def plot_KHD(hist_file, ax=None, number_mix_zones=8, xaxis='model_number'):
    """
    Makes a Kippenhahn plot from a provided history file
    ------- Parameters -------
    hist_file: String
        The path to the history file to be used for the plot.
    ax: an axis object
        Axes object on which the plot will be made. If None: make figure and axis within this function.
    number_mix_zones: int
        Number of mixing zones included in the mesa history file
    xaxis: String
        quantity to put on the x-axis of the plot (e.g. model_number or star_age)
    """
    if ax is None:
        fig = plt.figure( figsize=(10, 4))
        ax = fig.add_subplot(111)

    header, data = read_mesa_file(hist_file)

    xvals=data[xaxis]
    M_star = data['star_mass']
    M_ini  = M_star[0]

    N_mix = number_mix_zones
    for j in range(N_mix):
        colours = {'-1':'w', '0':'w', '1':'lightgrey', '2':'b', '7':'g', '3':'cornflowerblue', '8':'red'}
        if j == N_mix-1:
            ax.vlines(xvals, 0, data[f'mix_qtop_{N_mix-j}']*M_star/M_ini, color=[colours[str(x)] for x in data[f'mix_type_{N_mix-j}']])
        else:
            ax.vlines(xvals, data[f'mix_qtop_{N_mix-1-j}']*M_star/M_ini, data[f'mix_qtop_{N_mix-j}']*M_star/M_ini, color=[colours[str(x)] for x in data[f'mix_type_{N_mix-j}']])

    ax.plot(xvals, M_star / M_ini, lw=1, color='black', label=f'{M_ini:.1f} $M_\odot$')

    ax.set_xlim(min(xvals)*0.99, max(xvals)*1.01)
    ax.set_ylim(0, 1.02)

    ax.plot([], [], lw=10, color='lightgrey', label=r'Convective') # Only to make it appear in the Legend
    ax.plot([], [], lw=10, color='cornflowerblue', label=r'CBM')   # Only to make it appear in the Legend
    ax.legend(bbox_to_anchor=(0.15, 0.97), fontsize=10, frameon=False, fancybox=False, shadow=False, borderpad=False)
    ax.set_ylabel(r'Relative Mass $\, m/M_\star$')
    ax.set_xlabel(xaxis)
    plt.tight_layout()

    return

################################################################################
def calculate_number_densities(hist_file):
    '''
    Calculate surface number densities for all isotopes in the MESA grid.
    All isotopes in the used nuclear network need to be be written in the history file,
    otherwise this will function give wrong numbers.
    ------- Parameters -------
    hist_file: String
        The path to the MESA history file.
    ------- Returns -------
    number_densities: dictionary
        Column keys specify the element (surf_X_per_N_tot), values are number densities of that element.
    '''
    header, data = read_mesa_file(hist_file)
    element_list = {}
    number_densities = {}
    inverse_average_atomic_mass = np.zeros(len(data[ list(data.keys())[0] ]))
    for column_name in data.keys():
        if '_per_Mass_tot' in column_name:
            element_list.update({column_name: data[column_name]})
            inverse_average_atomic_mass += data[column_name]

    average_atomic_mass = inverse_average_atomic_mass**(-1)
    for key in element_list.keys():
        number_densities.update({ key.replace('_per_Mass_tot', '_per_N_tot') : element_list[key]*average_atomic_mass})

    return number_densities

################################################################################
def convert_units(quantity, input, convertto='cgs'):
    '''
    Converts from solar units to cgs and vice versa.
    ------- Parameters -------
    input: list of float
        Numbers to convert.
    quantity: string
        The quantity you want to convert. Options are: {radius, mass, luminosity}.
    convertto: string
        The unit system to convert to. Options are: {cgs,solar} with default: 'cgs'.
    ------- Returns -------
    out: list of float
        converted numbers
    '''
    # conversion factors used in MESA see $MESA_DIR/const/public/const_def.f90
    to_cgs = {'mass': 1.9892E33,
              'luminosity': 3.8418E33,
              'radius': 6.9598E10,
              'cgrav': 6.67428E-8} # gravitational constant (g^-1 cm^3 s^-2)

    # convert to cgs
    if convertto == 'cgs':
        return input * to_cgs[quantity]
    # convert to solar units
    elif convertto == 'solar':
        return input / to_cgs[quantity]

################################################################################
def grid_extract_spectroscopy(mesa_profiles, output_file='gridSpectroscopy.hdf', parameters=['Z', 'M', 'logD', 'aov', 'fov', 'Xc']):
    """
    Extract spectroscopic info and age for each globbed MESA profile and write them to 1 large file.
    ------- Parameters -------
    mesa_profiles: string
        String to glob to find all the relevant MESA profiles.
    output_file: string
        Name (or path) for the file containing all the pulsation frequencies of the grid.
    parameters: list of strings
        List of parameters varied in the computed grid, so these are taken from the
        name of the profile files, and included in the ouput file containing the info of the whole grid.
    """
    extract_func = partial(spectro_from_profiles, parameters=parameters)
    # Glob all the files, then iteratively send them to a pool of processors
    profiles = glob.iglob(mesa_profiles)
    with multiprocessing.Pool() as p:
        spectro = p.imap(extract_func, profiles)

        # Generate the directory for the output file and write the file afterwards
        Path(Path(output_file).parent).mkdir(parents=True, exist_ok=True)
        # make a new list, so 'parameters' is not extended before passing it on to 'spectro_from_profiles'
        header_parameters = list(parameters)
        header_parameters.extend(['logTeff', 'logL', 'logg', 'age'])

        # Make list of lists, put it in a dataframe, and write to a file
        data = []
        for line in spectro:
            data.append(line)

    df = pd.DataFrame(data=data, columns=header_parameters)
    df.to_hdf(f'{output_file}', 'spectrogrid', format='table', mode='w')


################################################################################
def spectro_from_profiles(mesa_profile, parameters):
    """
    Extract spectroscopic info and age from a MESA profile and the model parameters from its filename.
    ------- Parameters -------
    mesa_profile: string
        path to the MESA profile
    parameters: list of strings
        List of input parameters varied in the computed grid, so these are read from the filename and included in returned line.

    ------- Returns -------
    line: string
        Line containing all the model- and spectroscopic parameters of the MESA profile.
    """
    param_dict = sf.get_param_from_filename(mesa_profile, parameters,values_as_float=True)
    prof_header, prof_data = read_mesa_file(mesa_profile)

    logL = np.log10(float(prof_header['photosphere_L']))
    logTeff = np.log10(float(prof_header['Teff']))
    logg = prof_data['log_g'][0]
    age=int(float(prof_header['star_age']))

    line=[]
    for p in parameters:
        line.append(param_dict[p])
    line.extend([logTeff, logL, logg, age])
    return line

################################################################################
def add_spectro_to_puls_grid(grid_frequencies, grid_spectroscopy, output_name='grid_spectro+freq.hdf', model_parameters=['Z', 'M', 'logD', 'aov', 'fov', 'Xc']):
    """
    Combine the output files with the frequencies and spectroscopy of the grid in one new file,
    only keeping models that have entries in both the frequency and specto files.
    ------- Parameters -------
    grid_frequencies, grid_spectroscopy: string
        Paths to the files containing the model input parameters and corresponding frequency/spectroscopy of the model.
    output_name: string
        Name of the generated file containing the combined info.
    model_parameters: list of string
        List of the model parameters to use for matching the entries in the freq/spectro file.
    """
    freq_df    = pd.read_hdf(grid_frequencies)
    spectro_df = pd.read_hdf(grid_spectroscopy)
    # Merge with spectro info first, freq info second. Only keeping rows that both dataFrames have in common based on the 'on' columns.
    df_merged  = pd.merge(spectro_df, freq_df, how='inner', on=model_parameters)

    col = df_merged.pop("age") # Don't add the age in the combined file

    # take the column with rotation and place it as the first column, and its error as second column
    col = df_merged.pop("rot")
    df_merged.insert(0, col.name, col)
    col = df_merged.pop("rot_err")
    df_merged.insert(1, col.name, col)
    # write the merged dataFrame to a new file
    df_merged.to_hdf(f'{output_name}', 'puls_spectro_grid', format='table', mode='w')
