import crcmod
from selfdrive.car.hyundai.values import CAR, CHECKSUM, CAMERA_SCC_CAR

hyundai_checksum = crcmod.mkCrcFun(0x11D, initCrc=0xFD, rev=False, xorOut=0xdf)

def create_lkas11(packer, frame, car_fingerprint, apply_steer, steer_req,
                  torque_fault, lkas11, sys_warning, sys_state, enabled,
                  left_lane, right_lane,
                  left_lane_depart, right_lane_depart):
  values = lkas11
  values["CF_Lkas_LdwsSysState"] = sys_state
  values["CF_Lkas_SysWarning"] = 3 if sys_warning else 0
  values["CF_Lkas_LdwsLHWarning"] = left_lane_depart
  values["CF_Lkas_LdwsRHWarning"] = right_lane_depart
  values["CR_Lkas_StrToqReq"] = apply_steer
  values["CF_Lkas_ActToi"] = steer_req
  values["CF_Lkas_ToiFlt"] = torque_fault  # seems to allow actuation on CR_Lkas_StrToqReq
  values["CF_Lkas_MsgCount"] = frame % 0x10

  if car_fingerprint in (CAR.SONATA, CAR.PALISADE, CAR.KIA_NIRO_EV, CAR.KIA_NIRO_HEV_2021, CAR.SANTA_FE,
                         CAR.IONIQ_EV_2020, CAR.IONIQ_PHEV, CAR.KIA_SELTOS, CAR.ELANTRA_2021, CAR.GENESIS_G70_2020,
                         CAR.ELANTRA_HEV_2021, CAR.SONATA_HYBRID, CAR.KONA_EV, CAR.KONA_HEV, CAR.KONA_EV_2022,
                         CAR.SANTA_FE_2022, CAR.KIA_K5_2021, CAR.IONIQ_HEV_2022, CAR.SANTA_FE_HEV_2022, CAR.SANTA_FE_PHEV_2022):
    values["CF_Lkas_LdwsActivemode"] = int(left_lane) + (int(right_lane) << 1)
    values["CF_Lkas_LdwsOpt_USM"] = 2

    # FcwOpt_USM 5 = Orange blinking car + lanes
    # FcwOpt_USM 4 = Orange car + lanes
    # FcwOpt_USM 3 = Green blinking car + lanes
    # FcwOpt_USM 2 = Green car + lanes
    # FcwOpt_USM 1 = White car + lanes
    # FcwOpt_USM 0 = No car + lanes
    values["CF_Lkas_FcwOpt_USM"] = 2 if enabled else 1

    # SysWarning 4 = keep hands on wheel
    # SysWarning 5 = keep hands on wheel (red)
    # SysWarning 6 = keep hands on wheel (red) + beep
    # Note: the warning is hidden while the blinkers are on
    values["CF_Lkas_SysWarning"] = 4 if sys_warning else 0

  # Likely cars lacking the ability to show individual lane lines in the dash
  elif car_fingerprint in (CAR.KIA_OPTIMA_G4, CAR.KIA_OPTIMA_G4_FL):
    # SysWarning 4 = keep hands on wheel + beep
    values["CF_Lkas_SysWarning"] = 4 if sys_warning else 0

    # SysState 0 = no icons
    # SysState 1-2 = white car + lanes
    # SysState 3 = green car + lanes, green steering wheel
    # SysState 4 = green car + lanes
    values["CF_Lkas_LdwsSysState"] = 3 if enabled else 1
    values["CF_Lkas_LdwsOpt_USM"] = 2  # non-2 changes above SysState definition

    # these have no effect
    values["CF_Lkas_LdwsActivemode"] = 0
    values["CF_Lkas_FcwOpt_USM"] = 0

  elif car_fingerprint == CAR.HYUNDAI_GENESIS:
    # This field is actually LdwsActivemode
    # Genesis and Optima fault when forwarding while engaged
    values["CF_Lkas_LdwsActivemode"] = 2

  dat = packer.make_can_msg("LKAS11", 0, values)[2]

  if car_fingerprint in CHECKSUM["crc8"]:
    # CRC Checksum as seen on 2019 Hyundai Santa Fe
    dat = dat[:6] + dat[7:8]
    checksum = hyundai_checksum(dat)
  elif car_fingerprint in CHECKSUM["6B"]:
    # Checksum of first 6 Bytes, as seen on 2018 Kia Sorento
    checksum = sum(dat[:6]) % 256
  else:
    # Checksum of first 6 Bytes and last Byte as seen on 2018 Kia Stinger
    checksum = (sum(dat[:6]) + dat[7]) % 256

  values["CF_Lkas_Chksum"] = checksum

  return packer.make_can_msg("LKAS11", 0, values)


def create_clu11(packer, frame, clu11, button, car_fingerprint):
  values = clu11
  values["CF_Clu_CruiseSwState"] = button
  values["CF_Clu_AliveCnt1"] = frame % 0x10
  # send buttons to camera on camera-scc based cars
  bus = 2 if car_fingerprint in CAMERA_SCC_CAR else 0
  return packer.make_can_msg("CLU11", bus, values)


def create_lfahda_mfc(packer, enabled, hda_set_speed=0):
  values = {
    "LFA_Icon_State": 2 if enabled else 0,
    "HDA_Active": 1 if hda_set_speed else 0,
    "HDA_Icon_State": 2 if hda_set_speed else 0,
    "HDA_VSetReq": hda_set_speed,
  }
  return packer.make_can_msg("LFAHDA_MFC", 0, values)

def create_mdps12(packer, frame, mdps12):
  values = copy.copy(mdps12)
  values["CF_Mdps_ToiActive"] = 0
  values["CF_Mdps_ToiUnavail"] = 1
  values["CF_Mdps_MsgCount2"] = frame % 0x100
  values["CF_Mdps_Chksum2"] = 0

  dat = packer.make_can_msg("MDPS12", 2, values)[2]
  checksum = sum(dat) % 256
  values["CF_Mdps_Chksum2"] = checksum

  return packer.make_can_msg("MDPS12", 2, values)
def create_acc_commands(packer, enabled, accel, upper_jerk, idx, lead_visible, set_speed, stopping, long_override):
  commands = []

  scc11_values = {
    "MainMode_ACC": 1,
    "TauGapSet": 4,
    "VSetDis": set_speed if enabled else 0,
    "AliveCounterACC": idx % 0x10,
    "ObjValid": 1, # close lead makes controls tighter
    "ACC_ObjStatus": 1, # close lead makes controls tighter
    "ACC_ObjLatPos": 0,
    "ACC_ObjRelSpd": 0,
    "ACC_ObjDist": 1, # close lead makes controls tighter
    }
  commands.append(packer.make_can_msg("SCC11", 0, scc11_values))

  scc12_values = {
    "ACCMode": 2 if enabled and long_override else 1 if enabled else 0,
    "StopReq": 1 if stopping else 0,
    "aReqRaw": accel,
    "aReqValue": accel,  # stock ramps up and down respecting jerk limit until it reaches aReqRaw
    "CR_VSM_Alive": idx % 0xF,
  }
  scc12_dat = packer.make_can_msg("SCC12", 0, scc12_values)[2]
  scc12_values["CR_VSM_ChkSum"] = 0x10 - sum(sum(divmod(i, 16)) for i in scc12_dat) % 0x10

  commands.append(packer.make_can_msg("SCC12", 0, scc12_values))

  scc14_values = {
    "ComfortBandUpper": 0.0, # stock usually is 0 but sometimes uses higher values
    "ComfortBandLower": 0.0, # stock usually is 0 but sometimes uses higher values
    "JerkUpperLimit": upper_jerk, # stock usually is 1.0 but sometimes uses higher values
    "JerkLowerLimit": 5.0, # stock usually is 0.5 but sometimes uses higher values
    "ACCMode": 2 if enabled and long_override else 1 if enabled else 4, # stock will always be 4 instead of 0 after first disengage
    "ObjGap": 2 if lead_visible else 0, # 5: >30, m, 4: 25-30 m, 3: 20-25 m, 2: < 20 m, 0: no lead
  }
  commands.append(packer.make_can_msg("SCC14", 0, scc14_values))

  # note that some vehicles most likely have an alternate checksum/counter definition
  # https://github.com/commaai/opendbc/commit/9ddcdb22c4929baf310295e832668e6e7fcfa602
  fca11_values = {
    "CR_FCA_Alive": idx % 0xF,
    "PAINT1_Status": 1,
    "FCA_DrvSetStatus": 1,
    "FCA_Status": 1, # AEB disabled
  }
  fca11_dat = packer.make_can_msg("FCA11", 0, fca11_values)[2]
  fca11_values["CR_FCA_ChkSum"] = hyundai_checksum(fca11_dat[:7])
  commands.append(packer.make_can_msg("FCA11", 0, fca11_values))

  return commands

def create_acc_opt(packer):
  commands = []

  scc13_values = {
    "SCCDrvModeRValue": 2,
    "SCC_Equip": 1,
    "Lead_Veh_Dep_Alert_USM": 2,
  }
  commands.append(packer.make_can_msg("SCC13", 0, scc13_values))

  fca12_values = {
    "FCA_DrvSetState": 2,
    "FCA_USM": 1, # AEB disabled
  }
  commands.append(packer.make_can_msg("FCA12", 0, fca12_values))

  return commands

def create_frt_radar_opt(packer):
  frt_radar11_values = {
    "CF_FCA_Equip_Front_Radar": 1,
  }
  return packer.make_can_msg("FRT_RADAR11", 0, frt_radar11_values)
