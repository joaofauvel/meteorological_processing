from eto import ETo
from os.path import abspath
import pandas as pd
import datetime as dt
import math
import re
import logging


def print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█', print_end='\r'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
        printEnd    - Optional  : end character (e.g. "\r", "\r\n") (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    print(f'\r{prefix} |{bar}| {percent}% {suffix}', end=print_end)
    # Print New Line on Complete
    if iteration == total:
        print()


# Returns normalized pandas.DataFrame with specified columns, indexed by parsed dates.
def load_df(filepath, sep=';', decimal=',', date_columns=None, date_format='%Y-%m-%d %H%M',
            usecols=None, column_names=None):
    # Target column names. This is not the column names to be written to a file, but for in-program manipulation.
    if column_names is None:
        column_names = ['P', 'R_s', 'T_max', 'T_min', 'RH_max', 'RH_min', 'U_z']
    # Column indexes to use. Sets param usecols.
    if usecols is None:
        usecols = [0, 1, 3, 7, 11, 12, 16, 17, 21]
    # Indexes 0 and 1 and can be column names. Should be set with the argument parser options.
    if date_columns is None:
        date_columns = {'Date': [0, 1]}
    else:
        date_columns = {'Date': date_columns}

    # These parameters must be set by the argument parser options.
    # TODO: What is not set with a variable are likely defaults that should be set with arg parsing instead.
    df = pd.read_csv(filepath,
                     sep=sep, decimal=decimal,
                     parse_dates=date_columns,
                     date_parser=(lambda x: dt.datetime.strptime(x, date_format)),
                     skiprows=9,
                     header='infer',
                     index_col='Date',
                     usecols=usecols,
                     na_values=None,
                     keep_default_na=True)

    # Sets column names with the default layout to ones the ETo module can recognize.
    df.columns = column_names
    logging.info('Loaded csv file {}.'.format(filepath))
    return df


# Applies converters to df columns
def apply_conversion(df, converters=None, factors=None):
    # Conversions P: hPa/mB -> KPa; R_s: KJ/m2 -> MJ/m2.
    # TODO: Create conversion factors from argparse.
    if converters is None:
        converters = {'P': (lambda p: p / 10),
                      'R_s': (lambda r_s: r_s / 1000)}
    logging.info('Applied conversions.')
    df.loc[:, tuple(converters.keys())] = df.agg(converters)


# Returns localized or shifted df, optionally with dropped first and/or last day.
# TODO: Accounting for origin -> target TZ/time offset.
def localize(df, shift=-3, freq='1H', locale=None, drop_first=True, drop_last=True):
    logging.info('Time shifting dataframe: {} hours'.format(shift))
    logging.info('Localizing dataframe. Locale: {}'.format(locale))
    if shift and locale:
        raise Exception
    if shift:
        df = df.shift(-3, freq)
    elif locale:
        df.index = df.index.tz_localize('UTC').tz_convert('America/Sao_Paulo')

    # TODO: Support other frequencies.
    if drop_first:
        # Drop first day
        df.drop(df.loc[df.index.date == df.first('1H').index.date].index, inplace=True)
    if drop_last:
        # Drop last day
        df.drop(df.loc[df.index.date == df.last('1H').index.date].index, inplace=True)
    return df


def met_resample(df, freq='D'):
    df_daily_resample = df.resample(freq).agg({
        'P': 'mean',
        'R_s': 'sum',
        'T_max': 'max',
        'T_min': 'min',
        'RH_max': 'max',
        'RH_min': 'min',
        'U_z': 'mean',
    })
    return df_daily_resample


# Returns filled df.
# TODO: Interpolation, resampling and plot generation.
# TODO: Accept dict in method variable.
def fill_missing(df, method='6DH', fill_na=True, save_temp=True, missing_path=None):
    # Methods: linear interpolation, 6DH average (previous and next 3 day same hour avg), bfill, ffill.
    if missing_path:
        df = pd.read_csv(missing_path, parse_dates=['Date'], index_col='Date')
        logging.debug('Loaded file with missing data.')
        return df

    logging.debug('Forward filling same hour radiation data.')
    print_progress_bar(0, 24, prefix='Radiation ffill progress:', suffix='', length=30)
    for hour in range(24):
        # [df.index.time==dt.time(hour, 0), ('R_s')] -> mask for slicing the df. Returns the same hour for each day.
        df.loc[df.index.time == dt.time(hour, 0), 'R_s'] = df.loc[df.index.time == dt.time(hour, 0), 'R_s'].ffill()
        print_progress_bar(hour + 1, 24, prefix='Radiation ffill progress:', suffix='', length=30)
    if method == 'linear':
        logging.info('Interpolating missing data.')
        df.interpolate(method='time', inplace=True)
    elif method == '6DH':
        logging.debug('Filling missing data with 6DH method.')
        # Set the first day of the df
        current_day = df.iloc[0].name.date()
        # Calculate the number of days in the df
        days_in_df = math.ceil(len(df.index) / 24)

        print_progress_bar(0, days_in_df, prefix='6DH interpolation progress:', suffix='', length=30)
        # Iterate through each day
        for i in range(days_in_df):
            # Check for missing values in the R_s column for each day.
            # If there are missing values then calculate mean of the
            # previous and next 3 days for the same hour
            if df.loc[df.index.date == current_day].isna().values.any():
                # df of the day
                daily_df = df.loc[df.index.date == current_day]
                # Rows of missing hourly data df
                missing_daily = daily_df[daily_df.isna().any(axis=1)]

                # Get the df with interpolation data (previous and next 3 days)
                # and drop current day
                start_day = current_day - dt.timedelta(days=3)
                end_day = current_day + dt.timedelta(days=3)

                interp_df = df.loc[str(start_day):str(end_day)]
                interp_df = interp_df.drop(interp_df.loc[interp_df.index.date == current_day].index)

                # Iterate over the missing hours
                for date in missing_daily.index:
                    # Hourly df for the interpolation
                    hourly_df = interp_df.at_time(date.time())

                    missing_cols = missing_daily.at_time(date.time()).isna().any()
                    # If there are more than 2 missing data points in the hourly df,
                    # then use the mean monthly data
                    if hourly_df.isna().sum().max() > 2:
                        hourly_df = df.loc[
                            (df.index.month == current_day.month) & (df.index.year == current_day.year)].at_time(
                            date.time())

                    # Compute the mean for each missing column, leaving existing values,
                    # and concat interpolation into main df
                    df.loc[f'{str(current_day)} {date.time()}'].update(hourly_df.loc[:, missing_cols].mean())

            # Increment day
            current_day += dt.timedelta(days=1)
            print_progress_bar(i + 1, days_in_df, prefix='6DH interpolation progress:', suffix='', length=30)

    if fill_na:
        # Interpolate rest of na
        df.interpolate(method='time', inplace=True)
    logging.debug('Filled hourly df: \n{}'.format(df.head()))
    if save_temp:
        df.to_csv('temp_filled.csv')
        logging.info('Saved temporary dataframe with missing data in {}'.format(abspath('temp_filled.csv')))
    return df


def eto_calc(df, filepath=None, freq='D', parse_info_from_csv=True, z_msl=None, lat=None, lon=None, z_u=10):
    if parse_info_from_csv:
        if filepath:
            with open(filepath, 'r') as f:
                info = ''.join(map(str, [line for i, line in enumerate(f) if i < 9]))
                lat = float(re.search(r'Latitude: ([-\d.]+)', info).group(1))
                lon = float(re.search(r'Longitude: ([-\d.]+)', info).group(1))
                z_msl = float(re.search(r'Altitude: ([-\d.]+)', info).group(1))
        logging.info('Parsed site information for ETo calculation from csv. Lat: {}, Lon: {}, Alt: {}.'.format(lat,
                                                                                                               lon,
                                                                                                               z_msl))
    logging.debug('Columns in df: {}'.format(df.columns))
    logging.debug('Empty lines in df: \n{}'.format(df.isna().any()))
    logging.debug('df: \n{}'.format(df.head()))
    et1 = ETo()
    et1.param_est(df=df, freq=freq, z_msl=z_msl, lat=lat, lon=lon, z_u=z_u)
    eto1 = et1.eto_fao()

    return et1, eto1


# columns: list. Defines which columns and their disposition to export. If headers param is defined, then the columns
# are renamed, else export uses the default names.
# headers: list. Must have the same disposition and length as the columns param. If columns param is defined, then it
# renames columns before exporting, else the default column disposition is renamed.
# date_format: str. Date format to export.
# https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes
# conv_u: bool. Substitute the wind speed values to the converted wind speed at 2 meters. Requires the et dataframe.
# drop_rows: int. Default rows to drop from the export.
# eto: pandas.Series. ETo values to include in the export.
def write(df, filepath, et=None, eto=None, headers=None, columns=None, date_format=None, conv_u=True,
          drop_rows=None):
    if columns is None:
        columns = ['T_max', 'T_min', 'RH_max', 'RH_min', 'P', 'R_s', 'U_z', 'ETo_PM']
    if headers is None:
        headers = ['T_max (ºC)', 'T_min (ºC)', 'RH_max (%)', 'RH_min (%)', 'P (KPa)', 'R_g (MJ/m2/dia)', 'U_2 (m/s)',
                   'ETo_PM (mm/dia)']
    df_write = df
    if conv_u:
        if et is None:
            raise Exception
        else:
            df_write.loc[:, 'U_z'] = et.ts_param['U_2']

    if eto is not None:
        df_write.loc[:, 'ETo_PM'] = eto
    else:
        raise Exception

    df_write = df_write[columns]
    if headers and columns:
        df_write.rename(columns=dict(zip(columns, headers)), inplace=True)
    elif headers:
        df_write.rename(columns=headers, inplace=True)
    elif columns:
        df_write = df_write.reindex(columns=columns)

    if date_format:
        df_write.index = df_write.index.strftime(date_format)

    df_write.to_csv(filepath)
    logging.info('Exported csv to {}'.format(abspath(filepath)))


def main(args):
    df = load_df(args.i, sep=args.sep, decimal=args.dec, date_columns=args.date_columns_index,
                 date_format=args.date_format, usecols=args.usecols, column_names=args.column_names)
    df = localize(df, shift=args.time_shift, freq=args.freq, drop_first=args.no_drop_first, drop_last=args.no_drop_last)
    apply_conversion(df)
    df = fill_missing(df, method=args.fill_method, fill_na=args.no_fill_na, save_temp=args.no_save_temp,
                      missing_path=args.temp_file)
    df_daily = met_resample(df, freq=args.resample_freq)
    et, eto = eto_calc(df_daily, filepath=args.i, freq=args.resample_freq, parse_info_from_csv=args.no_infer_from_file,
                       z_msl=args.alt, lat=args.lat, lon=args.lon, z_u=args.z)
    write(df_daily, args.o, et, eto, headers=args.headers_export, columns=args.columns_export,
          date_format=args.date_format_export, conv_u=args.no_conv_z)


logging.basicConfig(level=logging.DEBUG)
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="""Processamento de dados meteorológicos horários para diários, 
    com cálculo de ETo. Parâmetros padrões para processamento de dados provenientes do BDMEP do INMET.""")
    parser.add_argument('i', type=str,
                        help='Caminho para o arquivo em csv para o processamento.')
    parser.add_argument('o', nargs='?', type=str,
                        help='Caminho para exportação. Padrão: processado.csv.', default='processado.csv')
    parser.add_argument('-f', '--freq', type=str, default='1H', help='Frequência dos dados brutos. Padrão: 1 hora.')
    parser.add_argument('--resample-freq', metavar='FREQ', type=str, default='D', help="""Frequência do resample
    dos dados. Utilizado no cálculo de ETo. Padrão: 1 dia.""")
    parser.add_argument('-s', '--sep', type=str, default=';', help='Delimitador de colunas do arquivo. Padrão: ";".')
    parser.add_argument('-d', '--dec', type=str, default=',', help="""Separador decimal utilizado no arquivo.
    Padrão: ",".""")
    parser.add_argument("--date-columns-index", metavar='I', action="extend", nargs="+", type=int, default=[0, 1],
                        help='Índices das colunas de data e hora. Padrão: --date-columns-index 0 1.')
    parser.add_argument('--date-format', metavar='FORMAT', type=str, default='%Y-%m-%d %H%M',
                        help="""Formato de data e hora. Veja os disponíveis aqui:
                        https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes. Padrão: 
                        Y-m-d HM (2010-12-31 1200).""")
    parser.add_argument("--usecols", metavar='I', action="extend", nargs="+", type=int,
                        default=[0, 1, 3, 7, 11, 12, 16, 17, 21],
                        help="""Índices das colunas para o processamento de dados. Precisa conter data e hora, pressão,
                        radiação global, temperaturas máxima e mínima ou média,
                        umidade relativa máxima e mínima ou média, e velocidade do vento. Padrão: --usecols 0 1 3 7 11
                        12 16 17 21.""")
    parser.add_argument("--column-names", metavar='NAME', action="extend", nargs="+", type=str,
                        default=['P', 'R_s', 'T_max', 'T_min', 'RH_max', 'RH_min', 'U_z'],
                        help="""Variáveis selecionadas pelo --usecols, exceto das colunas de data e hora. Padrão:
                        P R_s T_max T_min RH_max RH_min U_z.""")
    parser.add_argument('--time-shift', metavar='T', type=int, default=-3, help="""Valor para conversão de TZ. Padrão: 
    -3 horas.""")
    parser.add_argument('--no-drop-first', action='store_false',
                        help="""Se usado, não retira o primeiro dia de dados, após a conversão de TZ.""")
    parser.add_argument('--no-drop-last', action='store_false',
                        help="""Se usado, não retira o último dia de dados, após a conversão de TZ.""")
    parser.add_argument('--fill-method', type=str, default='6DH', choices=['6DH', 'linear'],
                        help='Método de preenchimento de lacunas de dados. Padrão: 6DH.')
    parser.add_argument('--no-fill-na', action='store_false', help="""Se usado, não preenche todo o restante dos dados
    com interpolação linear, após aplicação do método especificado pelo --fill-method.""")
    parser.add_argument('--no-save-temp', action='store_false', help="""Se usado, não salva um arquivo temporário.""")
    parser.add_argument('--temp-file', metavar='FILE', required=False, type=argparse.FileType('r'),
                        help="""Caminho para o arquivo temporário.""")
    parser.add_argument('--no-infer-from-file', action='store_false', help="""Se usado, não infere informações de 
    latitude, longitude e altitude do arquivo de dados.""")
    parser.add_argument('z', nargs='?', type=int, default=10,
                        help="""Altura da medição da velocidade do vento. Padrão: 10 metros.""")
    parser.add_argument('lat', nargs='?', type=float, help="""Latitude. 
    Apenas necessário se --no-infer-from-file for usado.""")
    parser.add_argument('lon', nargs='?', type=float, help="""Longitude. 
    Apenas necessário se --no-infer-from-file for usado.""")
    parser.add_argument('alt', nargs='?', type=float, help="""Altitude. 
    Apenas necessário se --no-infer-from-file for usado.""")
    parser.add_argument("--columns-export", metavar='NAME', action="extend", nargs="+", type=str,
                        default=['T_max', 'T_min', 'RH_max', 'RH_min', 'P', 'R_s', 'U_z', 'ETo_PM'],
                        help="""Variáveis e disposição que serão exportados, exceto data. Padrão: --columns-export T_max
                         T_min RH_max RH_min P R_s U_z ETo_PM.""")
    parser.add_argument("--headers-export", metavar='NAME', action="extend", nargs="+", type=str,
                        default=['T_max (ºC)', 'T_min (ºC)', 'RH_max (%)', 'RH_min (%)', 'P (KPa)', 'R_g (MJ/m2/dia)',
                                 'U_2 (m/s)', 'ETo_PM (mm/dia)'],
                        help="""Nomes das colunas que serão exportadas, exceto data. 
                        Disposição precisa ser a mesma que a especificada em --columns-export. Padrão: --headers-export 
                        T_max(ºC) T_min(ºC) RH_max(percent) RH_min(percent) P(KPa) R_g(MJ/m2/dia) U_2(m/s) ETo_PM(mm/dia).""")
    parser.add_argument('--date-format-export', metavar='FORMAT', type=str, default='%d/%m/%Y',
                        help="""Formato de data e hora para exportação. Veja os disponíveis aqui:
                            https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes. Padrão:
                            d/m/Y (31/12/2010).""")
    parser.add_argument('--no-conv-z', action='store_false',
                        help="""Se usado, a velocidade do vento não convertida para 2 metros é usada na exportação.""")
    # TODO: Setup verbose arg.
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='Detalhamento sobre a execução do programa.')
    # TODO: Setup log arg.
    parser.add_argument('-l', '--log', action='store_true', help='Cria arquivo de log.')

    main(parser.parse_args())

# TODO: Configure arg options for
# - File
# - sep and decimal params
# - Number of columns to skip
# - Drop head or tail n days or rows after header. Separate from skiprows param.
# - skiprows param.
# - TZ conversion: set origin and target TZ/time offset
# - Drop first and/or last day if there is TZ conversion. Default True and True
# - Which columns (index or label) and date format to use (include aliases for common formats).
#   Default {'Date' : [0, 1]} and %Y-%m-%d %H%M.
# - Which columns (index or label) are what variable. Default layout should be
#   P, R_s, T_max, T_min, RH_max, RH_min, U_z, in that order.
# - Column conversions to KPa and MJ/m2. Default converts P: hPa/mB -> KPa; R_s: KJ/m2 -> MJ/m2.
# - NA values to use and if should keep default
# - Print csv with hourly data
# - Column names to be written to file.
# TODO: Logging missing value days. Drop rows with missing values for ETo calculation.
