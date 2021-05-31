""" Top level script to run the pipeline sequentially, copy this script with the config file to the folder where you want to run the analysis.
Comment certain imports if you don't want to repeat them on repeated runs."""
import importlib
import config
# Check for sensible input, so that you don't use observed periods whilst looking at the theoretical values as if they are frequencies, and vice versa.
match_obsAndTheory = False
for obs_list in config.observable_list:
    for o in obs_list:
        if (config.periods_or_frequencies_observed) in o:
            match_obsAndTheory = True
    if match_obsAndTheory is False:
        config.logger.error(f'The observables that are analysed {config.observable_list} do not all include the observational data that is used: {config.periods_or_frequencies_observed}')
        sys.exit()
    match_obsAndTheory = False

importlib.import_module('pypulse.pipeline.0_extract_puls&spectro')
importlib.import_module('pypulse.pipeline.1_constuct_pattern')
importlib.import_module('pypulse.pipeline.2_calculate_likelihood')
importlib.import_module('pypulse.pipeline.3_spectroClip_AICc')
importlib.import_module('pypulse.pipeline.4_bestModel_errors')
importlib.import_module('pypulse.pipeline.5_correlationPlots')

importlib.import_module('pypulse.pipeline.table_bestModels')
