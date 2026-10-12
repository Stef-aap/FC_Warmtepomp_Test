#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 21 23:08:22 2026

@author: stef
"""
import numpy as np
import pandas as pd

import sys
from   pathlib            import Path
sys.path.append ( str ( Path.home() / "NC_Data/Data/Data_Python_25/SlimmeMeterPortal/Accu_Simu_Claude/" ) )
from Zon_History import KNMI_Get_QT_Year, Get_Month_PV_Uur_part, Calc_Month_Elektra

np.set_printoptions(precision=2, suppress=True)


# *********************************
# Graaddagen 2024 18/18 ??
# PV_perc per maand
# *********************************
Maand_Afkorting = "jan,feb,mrt,apr,mei,jun,jul,aug,sep,okt,nov,dec".split(',')


GraadDagen_pm_Volkel_2024_18_18 = np.array ([ 498, 318, 281, 169, 65, 60, 22, 6, 68, 187, 375, 428 ])
GraadDagen_pm_Volkel_2024_18_15 = np.array ([ 498, 318, 281, 164, 40, 46, 12, 0, 55, 174, 375, 428 ])
GraadDagen_pm                   = np.array ([ 498, 318, 281, 164, 40, 46, 12, 0, 55, 174, 375, 428 ])


#PV_perc_pm      = np.array ([3,    5,   8,   12,   13,   13, 
#                            13,   11,  10,    7,    3,    2 ] )
PV_perc_pm      = np.array ([ 1.9,  3.6, 8.1, 11.8, 14.9, 15.6, 
                             13.9, 12.7, 9.0,  4.7,  2.5,  1.4 ] )

GraadDagen_2024 = GraadDagen_pm.sum()
GD_perc_pm      = 100 * GraadDagen_pm / GraadDagen_2024 


# ****************************************************************************
# Met behulp van basis gegevens:
#   Afname
#   TerugLevering
#   PV_Wp of PV_KwH
# wordt verbruik per maand berekend en
# zelf verbruik van de opgewekte PV energie
# Deze class gebruikt geen KNMI gegevens, wel GraadDagen per maand
# ****************************************************************************
class EnergieSoort :
  def __init__ ( self, Name, Afname, Terug=0, *, PV_Wp=0, PV_kWh=0, kWh_per_Wp=None, Do_Print = False ) :
    self.Name           = Name
    self.Afname_pj      = Afname
    self.Terug_pj       = Terug
    
    if kWh_per_Wp : self.kWh_per_Wp = kWh_per_Wp
    else          : self.kWh_per_Wp = 0.93  #0.82
    
    if  PV_kWh > 0 : self.Opwek_pj = PV_kWh
    elif PV_Wp > 0 : self.Opwek_pj = self.kWh_per_Wp * PV_Wp
    self.PV_kWh = self.Opwek_pj
    self.PV_Wp  = int ( round ( self.Opwek_pj / self.kWh_per_Wp ) )
    
    self.Verbruik_pj    = self.Afname_pj + self.Opwek_pj - self.Terug_pj
    self.Eigen_Verbruik = 100 * ( self.Opwek_pj - self.Terug_pj ) / self.Opwek_pj

    if Do_Print :
      Eenheid = "kWh/jaar"
      print ( "\n========== New EnergieSoort %s ==========" % self.Name )
      print ( "%s Year        = %i" % ( self.Name, Year ) )
      print ( "%s Afname      = %i %s" % ( self.Name, round ( self.Afname_pj   ), Eenheid ) )
      if self.Opwek_pj > 0 :
        print ( "%s Terug       = %i %s" % ( self.Name, round ( self.Terug_pj    ), Eenheid ) )
        print ( "%s Opwek       = %i %s" % ( self.Name, round ( self.Opwek_pj    ), Eenheid ) )
        print ( "%s Verbruik    = %i %s" % ( self.Name, round ( self.Verbruik_pj ), Eenheid ) )
        print ( "%s PV Verbruik = %i %%" % ( self.Name, 
                                               round ( self.Eigen_Verbruik ) ) )
      print ()
    
    
  # *********************************************************
  # Method verdeeld Opwek en Verbruik over de 12 maanden
  # *********************************************************
  def Set_Base_pm ( self, Base_pm ) :
    self.Base_pm        = Base_pm

    self.Verbruik_GD_pj = self.Verbruik_pj - 12 * self.Base_pm
    self.Verbruik_GD_pm = self.Verbruik_GD_pj * GD_perc_pm / 100
    self.Verbruik_pm    = self.Verbruik_GD_pm + self.Base_pm
    #print ( "Elektra per Maand = " , np.round ( self.Verbruik_GD_pm + 
    #                                            self.Base_pm   ).astype(int) )

    self.Opwek_pm = self.Opwek_pj * PV_perc_pm / 100
    self.DF = pd.DataFrame ( { 
                             "Maand"       : Maand_Afkorting, 
                             "Base"        : 12 * [self.Base_pm],
                             "V_GD" : self.Verbruik_GD_pm, 
                             "V"    : self.Verbruik_pm,
                             "A-T"         : self.Verbruik_pm - self.Opwek_pm,



                             "Opwek"       : self.Opwek_pm,
                             
                             })
    #print ( self.DF )
    #print ()


  # *********************************************************
  # Afname + PV - Terug = Verbruik
  # We hebben deze gegevens per jaar, maar willen ze ook per maand weten.
  # We veronderstellen in eerste instantie dat het verbruik over de dag constant is
  # Verbruik_Dag = Verbruik_Maand / 30.5
  # Vervolgens kunnen we over alle dagen in iedere maand:
  # Per dag de PV vergeljken met het constante Verbruik
  #  - PV sommeren 
  #  - als PV > Verbruik, meetellen als Terug
  # we weten dan ook de Afname = Verbruik + Terug - PV
  # Vervolgens dagggevens van Afname, Terug, PV sommeren over de gehele maand
  # ToDO MAAND-LENGTE
  # *********************************************************
  def Add_KNMI_WP_Accu ( self, Year, *
                        ,Warmtepomp_kWh = -1
                        ,Accu_kWh       = 0
                        ,Accu_RTE       = 0.9
                        ,Do_Print       = False
                       ) :
    PV                = [] 
    Terug             = []
    Afname            = []
    Warmtepomp_Totaal = 0
    self.DF_KNMI      = pd.DataFrame ()
    
    # HIER JAAR DATA OPVRAGEN
    DF_Year = KNMI_Get_QT_Year ( Year, WeerStation="Volkel" )
    
    for Index in range ( 12 ) :
      #Verbruik     = self.DF [ "Verbruik" ] [ Index ]
      Verbruik     = self.DF [ "V" ] [ Index ]
      Month        = Index + 1
      GD_MaandDeel = GraadDagen_pm [ Month - 1 ] / GraadDagen_pm.sum()
      Warmtepomp   = GD_MaandDeel * Warmtepomp_kWh
      Warmtepomp_Totaal += Warmtepomp

      DF_i, PV_i, Terug_i, Afname_i = Calc_Month_Elektra ( DF_Year, Year, Month
                                                          ,Verbruik       = Verbruik
                                                          ,PV_Wp          = self.PV_Wp
                                                          ,Warmtepomp_kWh = Warmtepomp
                                                          ,Accu_kWh       = Accu_kWh
                                                          ,Accu_RTE       = Accu_RTE
                                                          ,Force_Rebuild  = False
                                                          )

      self.DF_KNMI = pd.concat ( [ self.DF_KNMI, DF_i ] )                                                      
      PV      .append ( PV_i     )
      Terug   .append ( Terug_i  )
      Afname  .append ( Afname_i )
      
      
    self.DF [ "Afname_K" ] = Afname
    self.DF [ "Terug_K"  ] = Terug
    self.DF [ "A-T_K"    ] = self.DF [ "Afname_K" ] - self.DF [ "Terug_K" ]
    self.DF [ "PV_K"     ] = PV
    self.DF [ "V_K" ] = self.DF["Afname_K"] + self.DF ["PV_K"] - self.DF["Terug_K"]
  
    # Maak een kopie om het origineel veilig te houden
    df_int = self.DF.copy ()
    # Zoek alle kolommen die getallen bevatten
    num_cols = df_int.select_dtypes ( include = "number" ).columns
    # Zet alleen die numerieke kolommen om naar integers
    df_int [ num_cols ] = round ( df_int [ num_cols ].fillna ( 0 ) ).astype ( int )

    if Do_Print :
      with pd.option_context ( "display.max_rows"      , None, 
                               "display.max_columns"   , None,
                               "display.large_repr"    , "truncate",
                               "display.max_categories", 12 ) :
        print ( df_int )
      print ()
  
    Eenheid = "kWh/jaar"
    #print ( "\n========== EnergieSoort %s uitgewerkt ==========" % self.Name )
    print ( "\n===================  Model   KNMI  ===============" )
    print ( "Year       = %i" % Year )
    print ( "Base_pm    = %4i kWh" % self.Base_pm )
    print ( "Warmtepomp = %4i kWh" % Warmtepomp_Totaal )
    print ( "Accu       = %4i kWh" % Accu_kWh )
    print ( "PV = %.2f kWh/Wp   %i Wp   %i kWh" % ( self.kWh_per_Wp,
                                                          self.PV_Wp, 
                                                          self.PV_kWh,
                                                          ) ) 
    print ( "%s Afname      = %4i   %4i   %s" % ( self.Name, round ( self.Afname_pj ), 
                                                df_int.Afname_K.sum(), Eenheid ) )
    if self.Opwek_pj > 0 :
      print ( "%s Terug       = %4i   %4i   %s" % ( self.Name, round ( self.Terug_pj ),
                                                  df_int.Terug_K.sum(), Eenheid ) )
      print ( "%s Afn-Terug   = %4i   %4i   %s" % ( self.Name, 
                                                  round ( self.Afname_pj - self.Terug_pj ),
                                                  df_int["A-T_K"].sum(), Eenheid ) )
      print ( "%s Opwek       = %i   %i   %s" % ( self.Name, round ( self.Opwek_pj ),
                                                  df_int.PV_K.sum(), Eenheid ) )
      print ( "%s Verbruik    = %i   %i   %s" % ( self.Name, round ( self.Verbruik_pj ),
                                                  df_int.V_K.sum(), Eenheid ) )
      print ( "%s PV Verbruik = %4i   %4i   %%" % ( self.Name, 
                                                  round ( self.Eigen_Verbruik ),
                                                  100 * ( df_int.PV_K.sum() - df_int.Terug_K.sum() ) / df_int.PV_K.sum() ) )
    print ()



def Main_Start () :  pass
""" *********************************************************************
# ***********************************************************************
# Main program
# ***********************************************************************
# ********************************************************************"""
if __name__ == "__main__":
  
  Tests = [ 1 ]
     
  if 1 in Tests :
    Year          = 2024
    
    Gas_m3        = 1200  # per jaar
    PV_kWh        = 2800  # per jaar
    #PV_Wp         = 3100
    kWh_per_Wp    = 0.94
    E_Afname_kWh  = 1915  # kWh per jaar
    E_Terug_kWh   = 1715  # kWh per jaar
    E_Base_kWh_pm = 172   # Stef augustus-2024
    
    
    # *****************************************
    # Gas-2-Elektra  hybr * Gas_m3 * G2E / SCOP
    # *****************************************
    Warmtepomp_kWh = 0.60 * 1200   * 10  / 4
    Accu_kWh       = 10
    Accu_RTE       = 0.9    
    
    #for PV_kWh in [ 2600, 2700, 2800, 2900, 3000 ] :
    #for E_Base_kWh_pm in [ 130, 150, 170, 190, 210 ] :
    if True :
      Elektra = EnergieSoort ( "Elektra"
                              ,E_Afname_kWh
                              ,E_Terug_kWh
                              ,PV_kWh     = PV_kWh
                              ,kWh_per_Wp = kWh_per_Wp )

      Elektra.Set_Base_pm ( E_Base_kWh_pm )           
      
      Elektra.Add_KNMI_WP_Accu ( Year
                                ,Warmtepomp_kWh = 0
                                ,Accu_kWh       = 0
                                ,Accu_RTE       = Accu_RTE
                                ,Do_Print       = False
                               )
      Elektra.Add_KNMI_WP_Accu ( Year
                                ,Warmtepomp_kWh = Warmtepomp_kWh
                                ,Accu_kWh       = 0
                                ,Accu_RTE       = Accu_RTE
                                ,Do_Print       = False
                               )
      Elektra.Add_KNMI_WP_Accu ( Year
                                ,Warmtepomp_kWh = Warmtepomp_kWh
                                ,Accu_kWh       = Accu_kWh
                                ,Accu_RTE       = Accu_RTE
                                ,Do_Print       = False
                               )

    
  
"""
===================  Model   KNMI  ===============
Year       = 2024
Base_pm    =  172 kWh
Warmtepomp =    0 kWh
Accu       =    0 kWh
PV = 0.94 kWh/Wp   2979 Wp   2800 kWh
Elektra Afname      = 1915   2011   kWh/jaar
Elektra Terug       = 1715   1721   kWh/jaar
Elektra Afn-Terug   =  200    292   kWh/jaar
Elektra Opwek       = 2800   2707   kWh/jaar
Elektra Verbruik    = 3000   3001   kWh/jaar
Elektra PV Verbruik =   39     36   %


===================  Model   KNMI  ===============
Year       = 2024
Base_pm    =  172 kWh
Warmtepomp = 1800 kWh
Accu       =    0 kWh
PV = 0.94 kWh/Wp   2979 Wp   2800 kWh
Elektra Afname      = 1915   3618   kWh/jaar
Elektra Terug       = 1715   1526   kWh/jaar
Elektra Afn-Terug   =  200   2092   kWh/jaar
Elektra Opwek       = 2800   2707   kWh/jaar
Elektra Verbruik    = 3000   4802   kWh/jaar
Elektra PV Verbruik =   39     43   %


===================  Model   KNMI  ===============
Year       = 2024
Base_pm    =  172 kWh
Warmtepomp = 1800 kWh
Accu       =   10 kWh
PV = 0.94 kWh/Wp   2979 Wp   2800 kWh
Elektra Afname      = 1915   2905   kWh/jaar
Elektra Terug       = 1715    753   kWh/jaar
Elektra Afn-Terug   =  200   2152   kWh/jaar
Elektra Opwek       = 2800   2707   kWh/jaar
Elektra Verbruik    = 3000   4858   kWh/jaar
Elektra PV Verbruik =   39     72   %

%runfile /home/stef/NC_Data/Data/Data_Python_25/Web_Excel/GraadDagen_PVopbrengst.py --wdir
Reloaded modules: Zon_History
   Maand  Base  V_GD    V  A-T  Opwek  Afname_K  Terug_K  A-T_K  PV_K  V_K
0    jan   172   195  367  314     53       307       11    296    71  367
1    feb   172   124  296  196    101       233       14    219    77  296
2    mrt   172   110  282   55    227       178       96     83   199  282
3    apr   172    64  236  -94    330       125      196    -71   307  236
4    mei   172    16  188 -230    417        86      277   -191   378  188
5    jun   172    18  190 -247    437        79      312   -233   423  190
6    jul   172     5  177 -213    389        75      312   -237   414  177
7    aug   172     0  172 -184    356        80      311   -231   403  172
8    sep   172    22  194  -58    252       108      180    -72   265  194
9    okt   172    68  240  109    132       162       70     92   148  240
10   nov   172   147  319  249     70       263       11    252    66  319
11   dec   172   168  340  300     39       307        1    306    34  340



Stef: 8 panelen 245 Wp = 1960, 3 * 93Wp, 3 * 205 Wp, totaal 2854 Wp
2013 = 2339 kWh (82%)

2014 = 2390 kWh (84%)
Later nog panelen op de schuur die heel ongustig liggen, naar schatting 146 Wp
Totaal dus 3000 Wp, levert 80% .. 85% = 2400kWh ... 2550 kWh


3000 Wp, Zuid, 35 graden
JaarGeschatte opbrengstKenmerken van het zonnejaar
2020~2.850 kWh, Extreem zonnig. Vooral een legendarisch zonnig en warm voorjaar 
                (tijdens de eerste lockdown) zorgde voor topopbrengsten.
2021~2.500 kWh, Somber en koel. Dit was het minst productieve jaar in deze reeks 
                door een natte zomer en grijze maanden.
2022~3.050 kWh, Het absolute recordjaar. Het zonnigste jaar ooit gemeten door het KNMI. 
                Jouw installatie heeft dit jaar waarschijnlijk de 
                magische grens van 3.000 kWh doorbroken.
2023~2.750 kWh, Zeer goed jaar. Ondanks een wisselvallige zomer zorgden een extreem zonnige juni en 
                een prima najaar voor prima resultaten.
2024-2.600 kWh, Matig/Normaal jaar. 
                Zoals besproken: een erg nat voorjaar drukte de opbrengst met 
                zo'n 6% ten opzichte van het jaar ervoor [1.23].
2025~2.900 kWh, Uitzonderlijk zonnig. Na 2022 was 2025 het op één na zonnigste jaar 
                sinds het begin van de metingen. 
                De panelen profiteerden van een zonovergoten lente en zomer.
"""