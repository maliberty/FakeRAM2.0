import os
import sys
import math

################################################################################
# CREATE LEF view for the given SRAM
################################################################################

def create_lef( mem ):

    # File pointer
    fid = open(os.sep.join([mem.results_dir, mem.name + '.lef']), 'w')

    # Memory parameters
    name        = mem.name
    depth       = mem.depth
    bits        = mem.width_in_bits
    w           = mem.width_um 
    h           = mem.height_um
    num_rwport  = mem.rw_ports
    addr_width  = math.ceil(math.log2(mem.depth))

    # Process parameters
    min_pin_width   = mem.process.pin_width_um
    min_pin_pitch   = mem.process.pin_pitch_um
    manufacturing_grid_um = mem.process.manufacturing_grid_um
    metal_prefix     = mem.process.metal_prefix
    metal_layer      = mem.process.metal_layer
    column_mux_factor = mem.process.column_mux_factor
 
    # Offset from bottom edge to first pin
    x_offset = 1 * min_pin_pitch   ;# as told by MSK 
    y_offset = 1 * min_pin_pitch   ;# as told by MSK 
    #########################################
    # Calculate the pin spacing (pitch)
    #########################################
    number_of_pins = 2*bits + addr_width + 3
    #number_of_pins = 3*bits + addr_width + 3 # 3 * bits -> write data, read data, write mask; + 3 -> clk, we_i, ce_i
    number_of_tracks_available = math.floor((h - 2*y_offset) / min_pin_pitch)
    number_of_spare_tracks = number_of_tracks_available - number_of_pins

    if number_of_spare_tracks < 0:
        print("Error: not enough tracks (num pins: %d, available tracks: %d)." % (number_of_pins, number_of_tracks_available))
        sys.exit(1)

    ## The next few lines of code till "pin_pitch = min.." spreads the pins in higher multiples of pin pitch if there are available tracks
    track_count = 1
    while number_of_spare_tracks > 0:
        track_count += 1
        number_of_spare_tracks = number_of_tracks_available - number_of_pins*track_count
    track_count -= 1

    pin_pitch = min_pin_pitch * track_count
    #group_pitch = math.floor((number_of_tracks_available - number_of_pins*track_count) / 4)*mem.process.pin_pitch_um #what is this / 4 ?
    ## the following 4 lines are changes made by JC
    extra = math.floor((number_of_tracks_available - number_of_pins*track_count) / 4)
    if extra == 0:
        extra = 1
    group_pitch = extra*mem.process.pin_pitch_um
    #########################################
    # LEF HEADER
    #########################################

    fid.write('VERSION 5.7 ;\n')
    fid.write('BUSBITCHARS "[]" ;\n')
    fid.write('MACRO %s\n' % (name))
    fid.write('  FOREIGN %s 0 0 ;\n' % (name))
    fid.write('  SYMMETRY X Y R90 ;\n')
    fid.write('  SIZE %.3f BY %.3f ;\n' % (w,h))
    fid.write('  CLASS BLOCK ;\n')

    ########################################
    # LEF SIGNAL PINS
    ########################################

    y_step = y_offset - (y_offset % manufacturing_grid_um) + (mem.process.pin_width_um/2.0)
    #for i in range(int(bits)) :
    #    y_step = lef_add_pin( fid, mem, 'w_mask_in[%d]'%i, True, y_step, pin_pitch ) # lef_add_pin returns y_step + pitch; essentially y_step = y_step + pitch

    #y_step += group_pitch-pin_pitch # why is this required ? I think what is happening that the types of pins are divided into 5 groups : w_mask bus, rd_out bus, wd_in bus, addr_in bus and misc. These "groups" are not separated by the pin_pitch, rather they're separated by more distance ( a function of group_pitch and pin pitch )
    for i in range(int(bits)) :
        y_step = lef_add_pin( fid, mem, 'rd_out[%d]'%i, False, y_step, pin_pitch )

    y_step += group_pitch-pin_pitch
    for i in range(int(bits)) :
        y_step = lef_add_pin( fid, mem, 'wd_in[%d]'%i, True, y_step, pin_pitch )

    y_step += group_pitch-pin_pitch
    for i in range(int(addr_width)) :
        y_step = lef_add_pin( fid, mem, 'addr_in[%d]'%i, True, y_step, pin_pitch )

    y_step += group_pitch-pin_pitch
    y_step = lef_add_pin( fid, mem, 'we_in', True, y_step, pin_pitch )
    y_step = lef_add_pin( fid, mem, 'ce_in', True, y_step, pin_pitch )
    y_step = lef_add_pin( fid, mem, 'clk',   True, y_step, pin_pitch )

    ########################################
    # Create VDD/VSS Strapes
    ########################################

    supply_pin_width = min_pin_width*4
    supply_pin_half_width = supply_pin_width/2
    supply_pin_pitch = min_pin_pitch*8
    #supply_pin_layer = '%s' % metal_layer

    ## Create supply pins  : HOW'RE we ensuring that supply pins don't overlap with the signal pins ? Is it by giving x_offset as the base x coordinate ?
    y_step = y_offset
    fid.write('  PIN VSS\n')
    fid.write('    DIRECTION INOUT ;\n')
    fid.write('    USE GROUND ;\n')
    fid.write('    PORT\n')
    fid.write('      LAYER %s ;\n' % metal_layer)
    while y_step <= h - y_offset:
        fid.write('      RECT %.3f %.3f %.3f %.3f ;\n' % (x_offset, y_step-supply_pin_half_width, w-x_offset, y_step+supply_pin_half_width))
        y_step += supply_pin_pitch*2 # this *2 is important because we want alternate VDD and VSS pins
    fid.write('    END\n')
    fid.write('  END VSS\n')

    y_step = y_offset + supply_pin_pitch
    fid.write('  PIN VDD\n')
    fid.write('    DIRECTION INOUT ;\n')
    fid.write('    USE POWER ;\n')
    fid.write('    PORT\n')
    fid.write('      LAYER %s ;\n' % metal_layer)
    while y_step <= h - y_offset:
        fid.write('      RECT %.3f %.3f %.3f %.3f ;\n' % (x_offset, y_step-supply_pin_half_width, w-x_offset, y_step+supply_pin_half_width))
        y_step += supply_pin_pitch*2
    fid.write('    END\n')
    fid.write('  END VDD\n')

    ########################################
    # Create obstructions
    ########################################

    fid.write('  OBS\n')

    # full rect
    pin_layer_number = metal_layer.replace(metal_prefix, "", 1)
    print("Pin layer number is", pin_layer_number)
    for x in range(int(pin_layer_number)) :
      dummy = x + 1
      fid.write('    LAYER %s%d ;\n' % (metal_prefix,dummy))
      fid.write('    RECT 0 0 %.3f %.3f ;\n' % (w,h))

    fid.write('  END\n')
    fid.write('END %s\n' % name)
    fid.write('\n')
    fid.write('END LIBRARY\n')
    fid.close()

#
# Helper function that adds a signal pin
# y_step = lef_add_pin( fid, mem, 'w_mask_in[%d]'%i, True, y_step, pin_pitch )
def lef_add_pin( fid, mem, pin_name, is_input, y, pitch ):

  layer = mem.process.metal_layer
  pw  = mem.process.pin_width_um
  hpw = (mem.process.pin_width_um/2.0) ;# half pin width

  fid.write('  PIN %s\n' % pin_name)
  fid.write('    DIRECTION %s ;\n' % ('INPUT' if is_input else 'OUTPUT'))
  fid.write('    USE SIGNAL ;\n')
  fid.write('    SHAPE ABUTMENT ;\n')
  fid.write('    PORT\n')
  fid.write('      LAYER %s ;\n' % layer)
  fid.write('      RECT %.3f %.3f %.3f %.3f ;\n' % (0, y-hpw, pw, y+hpw))
  fid.write('    END\n')
  fid.write('  END %s\n' % pin_name)
  
  return y + pitch
