# meteorological_processing
	usage: processing.py [-h] [-f FREQ] [--resample-freq FREQ] [-s SEP] [-d DEC] [--conv-p CONV_P]
	                     [--conv-rs CONV_RS] [--date-columns-index I [I ...]] [--date-format FORMAT]
	                     [--usecols I [I ...]] [--column-names NAME [NAME ...]] [--time-shift T]
	                     [--no-drop-first] [--no-drop-last] [--fill-method {6DH,linear}] [--no-fill-na]
	                     [--no-fill-na-at-all] [--skip-rows SKIP_ROWS] [--no-save-temp]
	                     [--temp-file FILE] [--no-infer-from-file] [--columns-export NAME [NAME ...]]
	                     [--headers-export NAME [NAME ...]] [--date-format-export FORMAT] [--no-conv-z]
	                     [-v] [-l]
	                     i [o] [z] [lat] [lon] [alt] [tz]
	
	Processamento de dados meteorológicos horários para diários, com cálculo de ETo. Parâmetros padrões
	para processamento de dados provenientes do BDMEP do INMET.
	
	positional arguments:
	  i                     Caminho para o arquivo em csv para o processamento.
	  o                     Caminho para exportação. Padrão: processado.csv.
	  z                     Altura da medição da velocidade do vento. Padrão: 10 metros.
	  lat                   Latitude. Apenas necessário se --no-infer-from-file for usado.
	  lon                   Longitude. Apenas necessário se --no-infer-from-file for usado.
	  alt                   Altitude. Apenas necessário se --no-infer-from-file for usado.
	  tz                    Fuso horário onde os dados foram coletados. Não altera o cálculo de
	                        evapotranspiração, diferemente de --time-shift. Padrão: -3.
	
	optional arguments:
	  -h, --help            show this help message and exit
	  -f FREQ, --freq FREQ  Frequência dos dados brutos. Padrão: 1 hora.
	  --resample-freq FREQ  Frequência do resample dos dados. Utilizado no cálculo de ETo. Padrão: 1
	                        dia.
	  -s SEP, --sep SEP     Delimitador de colunas do arquivo. Padrão: ";".
	  -d DEC, --dec DEC     Separador decimal utilizado no arquivo. Padrão: ",".
	  --conv-p CONV_P       Fator de conversão para a pressão. Padrão: 10.0.
	  --conv-rs CONV_RS     Fator de conversão para a radiação global. Padrão: 1000.0.
	  --date-columns-index I [I ...]
	                        Índices das colunas de data e hora. Padrão: --date-columns-index 0 1.
	  --date-format FORMAT  Formato de data e hora. Veja os disponíveis aqui:
	                        https://docs.python.org/3/library/datetime.html#strftime-and-strptime-
	                        format-codes. Padrão: Y-m-d HM (2010-12-31 1200).
	  --usecols I [I ...]   Índices das colunas para o processamento de dados. Precisa conter data e
	                        hora, pressão, radiação global, temperaturas máxima e mínima ou média,
	                        umidade relativa máxima e mínima ou média, e velocidade do vento. Padrão:
	                        --usecols 0 1 3 7 11 12 16 17 21.
	  --column-names NAME [NAME ...]
	                        Variáveis selecionadas pelo --usecols, exceto das colunas de data e hora.
	                        Padrão: P R_s T_max T_min RH_max RH_min U_z.
	  --time-shift T        Valor para conversão de TZ. Padrão: -3 horas.
	  --no-drop-first       Se usado, não retira o primeiro dia de dados, após a conversão de TZ.
	  --no-drop-last        Se usado, não retira o último dia de dados, após a conversão de TZ.
	  --fill-method {6DH,linear}
	                        Método de preenchimento de lacunas de dados. Padrão: 6DH.
	  --no-fill-na          Se usado, não preenche todo o restante dos dados com interpolação linear,
	                        após aplicação do método especificado pelo --fill-method.
	  --no-fill-na-at-all   Se usado, não aplica método de preenchimento.
	  --skip-rows SKIP_ROWS
	                        Pula linhas a partir do ínício do arquivo. Utilize o número de linhas do
	                        cabeçalho até o início dos dados. Padrão: 9.
	  --no-save-temp        Se usado, não salva um arquivo temporário.
	  --temp-file FILE      Caminho para o arquivo temporário.
	  --no-infer-from-file  Se usado, não infere informações de latitude, longitude e altitude do
	                        arquivo de dados.
	  --columns-export NAME [NAME ...]
	                        Variáveis e disposição que serão exportados, exceto data. Padrão: --columns-
	                        export T_max T_min RH_max RH_min P R_s U_z ETo_PM.
	  --headers-export NAME [NAME ...]
	                        Nomes das colunas que serão exportadas, exceto data. Disposição precisa ser
	                        a mesma que a especificada em --columns-export. Padrão: --headers-export
	                        T_max(ºC) T_min(ºC) RH_max(percent) RH_min(percent) P(KPa) R_g(MJ/m2/dia)
	                        U_2(m/s) ETo_PM(mm/dia).
	  --date-format-export FORMAT
	                        Formato de data e hora para exportação. Veja os disponíveis aqui:
	                        https://docs.python.org/3/library/datetime.html#strftime-and-strptime-
	                        format-codes. Padrão: d/m/Y (31/12/2010).
	  --no-conv-z           Se usado, a velocidade do vento não convertida para 2 metros é usada na
	                        exportação.
	  -v, --verbose         Detalhamento sobre a execução do programa.
	  -l, --log             Cria arquivo de log.
