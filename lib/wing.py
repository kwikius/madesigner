#!python

__author__ = "Curtis L. Olson < curtolson {at} flightgear {dot} org >"
__url__ = "http://gallinazo.flightgear.org"
__version__ = "1.0"
__license__ = "GPL v2"


import copy
import math

try:
    import svgwrite
except ImportError:
    import sys, os
    sys.path.insert(0, os.path.abspath(os.path.split(os.path.abspath(__file__))[0]+'/..'))
    import svgwrite

import airfoil
import contour
import layout
import spline


class Rib:
    def __init__(self):
        self.thickness = 0.0625
        self.material = "balsa"
        self.contour = None
        self.pos = (0.0, 0.0, 0.0)
        self.twist = 0.0
        self.placed = False


class Stringer:
    def __init__(self, cutout=None, start_station=None, end_station=None):
        self.cutout = cutout
        self.start_station = start_station
        self.end_station = end_station


class TrailingEdge:
    def __init__(self, width=0.0, height=0.0, shape="", \
                     start_station=None, end_station=None):
        self.width = width
        self.height = height
        self.shape = shape
        self.start_station = start_station
        self.end_station = end_station


class Flap:
    def __init__(self, start_station=None, end_station=None, \
                     pos=None):
        self.start_station = start_station
        self.end_station = end_station
        self.pos = pos


class Wing:

    def __init__(self):
        self.units = "in"

        # wing layout
        self.root = None        # Airfoil()
        self.tip = None         # Airfoil()
        self.root_yscale = 1.0
        self.tip_yscale = 1.0
        self.span = 0.0
        self.twist = 0.0
        self.stations = []      # 1D array of rib positions
        self.sweep = None       # Contour()
        self.taper = None       # Contour()

        # structural components
        self.steps = 10
        self.leading_edge_diamond = 0.0
        self.trailing_edges = []
        self.stringers = []
        self.spars = []
        self.flaps = []

        # generated parts
        self.right_ribs = []
        self.left_ribs = []

    def load_airfoils(self, root, tip = None):
        self.root = airfoil.Airfoil(root, 1000, True)
        if tip:
            self.tip = airfoil.Airfoil(tip, 1000, True)

    # define the rib 'stations' as evenly spaced
    def set_num_stations(self, count):
        if count <= 0:
            print "Must specify a number of stations > 0"
            return
        if self.span < 0.01:
            print "Must set wing.span value before computing stations"
            return
        dp = 1.0 / count
        for p in range(0, count+1):
            print p
            percent = p * dp
            lat_dist = self.span * percent
            self.stations.append( lat_dist )

    # define the rib 'stations' explicitely as an array of locations
    def set_stations(self, stations):
        if len(stations) < 2:
            print "Must specify a list of at least 2 station positions"
            return
        self.stations = stations

    # define a fixed sweep angle
    def set_sweep_angle(self, angle):
        if self.span < 0.01:
            print "Must set wing.span value before sweep angle"
            return
        tip_offset = self.span * math.tan(math.radians(angle))
        self.sweep = contour.Contour()
        self.sweep.top.append( (0.0, 0.0) )
        self.sweep.top.append( (self.span, tip_offset) )

    # define a sweep reference contour (plotted along 25% chord).  It is
    # up to the calling function to make sure the first and last "x"
    # coordinates match up with the root and tip measurements of the wing
    # curve is a list of point pair ( (x1, y1), (x2, y2) .... )
    def set_sweep_curve(self, curve):
        self.sweep = contour.Contour()
        self.sweep.top = curve

    # define the wing chord (and optionally a separate tip chord for
    # linear taper)
    def set_chord(self, root_chord, tip_chord = 0.0):
        if self.span < 0.01:
            print "Must set wing.span value before chord"
            return
        self.taper = contour.Contour()
        self.taper.top.append( (0.0, root_chord) )
        if tip_chord < 0.1:
            self.taper.top.append( (self.span ,root_chord) )
        else:
            self.taper.top.append( (self.span ,tip_chord) )

    def set_taper_curve(self, curve):
        self.taper = contour.Contour()
        self.taper.top = curve

    def add_trailing_edge(self, width=0.0, height=0.0, shape="", \
                         start_station=None, end_station=None):
        te = TrailingEdge( width, height, shape, start_station, end_station )
        self.trailing_edges.append( te )

    def add_stringer(self, side="top", orientation="tangent", \
                         percent=None, front=None, rear=None, center=None, \
                         xsize=0.0, ysize=0.0, \
                         start_station=None, end_station=None):
        cutpos = contour.Cutpos( percent, front, rear, center )
        cutout = contour.Cutout( side, orientation, cutpos, xsize, ysize )
        stringer = Stringer( cutout, start_station, end_station )
        self.stringers.append( stringer )

    def add_spar(self, side="top", orientation="vertical", \
                     percent=None, front=None, rear=None, center=None, \
                     xsize=0.0, ysize=0.0, \
                     start_station=None, end_station=None):
        cutpos = contour.Cutpos( percent, front, rear, center )
        cutout = contour.Cutout( side, orientation, cutpos, xsize, ysize )
        spar = Stringer( cutout, start_station, end_station )
        self.spars.append( spar )

    def add_flap(self, start_station=None, end_station=None, \
                     pos=None, type="builtup", edge_stringer_size=None):
        flap = Flap( start_station, end_station, pos )
        self.flaps.append( flap )
        if edge_stringer_size != None:
            double_width = edge_stringer_size[0] * 2.0
            #front_pos = copy.deepcopy(pos)
            #front_pos.move(-half_offset)
            topcutout = contour.Cutout( side="top", orientation="tangent", \
                                            cutpos=pos, \
                                            xsize=double_width, \
                                            ysize=edge_stringer_size[1] )
            stringer = Stringer( topcutout, start_station, end_station )
            self.stringers.append( stringer )

            botcutout = contour.Cutout( side="bottom", orientation="tangent", \
                                            cutpos=pos, \
                                            xsize=double_width, \
                                            ysize=edge_stringer_size[1] )
            stringer = Stringer( botcutout, start_station, end_station )
            self.stringers.append( stringer )

            #half_offset = edge_stringer_size[0] * 0.5
            #rear_pos = copy.deepcopy(pos)
            #rear_pos.move(half_offset)
            #topcutout = contour.Cutout( side="top", orientation="tangent", \
            #                                cutpos=rear_pos, \
            #                                xsize=edge_stringer_size[0], \
            #                                ysize=edge_stringer_size[1] )
            #stringer = Stringer( topcutout, start_station, end_station )
            #self.stringers.append( stringer )

    # return true of lat_dist is between station1 and station2, inclusive.
    # properly handle cases where station1 or station2 is not defined (meaning
    # all the way to the end.
    def match_station(self, start_dist, end_dist, lat_dist):
        result = True
        abs_lat = math.fabs(lat_dist)
        if start_dist != None:
            if start_dist - abs_lat > 0.01:
                result = False
        if end_dist != None:
            if abs_lat - end_dist > 0.01:
                result = False
        return result
            
    def make_raw_rib(self, airfoil, chord, lat_dist, sweep_dist, twist, label ):
        result = Rib()
        result.contour = copy.deepcopy(airfoil)

        # scale and position
        result.contour.scale(chord, chord)
        result.contour.fit(500, 0.002)
        result.contour.move(-0.25*chord, 0.0)
        result.contour.save_bounds()

        # add label (before rotate)
        posx = 0.0
        ty = result.contour.simple_interp(result.contour.top, posx)
        by = result.contour.simple_interp(result.contour.bottom, posx)
        posy = by + (ty - by) / 2.0
        result.contour.add_label( posx, posy, 14, 0, label )

        # set plan position & twist
        result.pos = (lat_dist, sweep_dist, 0.0)
        result.twist = twist

        return result

    def make_rib_cuts(self, rib ):
        lat_dist = rib.pos[0]
        chord = rib.contour.saved_bounds[1][0] - rib.contour.saved_bounds[0][0]

        # leading edge cutout
        diamond = self.leading_edge_diamond
        if diamond > 0.01:
            rib.contour.cutout_leading_edge_diamond(diamond)

        # cutout stringers (before twist)
        for stringer in self.stringers:
            if self.match_station(stringer.start_station, stringer.end_station, lat_dist):
                rib.contour.cutout_stringer( stringer.cutout )

        # trailing edge cutout
        for te in self.trailing_edges:
            if self.match_station(te.start_station, te.end_station, lat_dist):
                rib.contour.cutout_trailing_edge( te.width, te.height, \
                                                         te.shape )

        # do rotate
        rib.contour.rotate(rib.twist)

        # cutout spars (stringer cut after twist)
        for spar in self.spars:
            if self.match_station(spar.start_station, spar.end_station, lat_dist):
                rib.contour.cutout_stringer( spar.cutout )

    def build(self):
        if len(self.stations) < 2:
            print "Must define at least 2 stations to build a wing"
            return

        sweep_y2 = spline.derivative2( self.sweep.top )
        taper_y2 = spline.derivative2( self.taper.top )

        for index, station in enumerate(self.stations):
            percent = station / self.span

            # generate airfoil
            if not self.tip:
                af = self.root
            else:
                af = airfoil.blend(self.root, self.tip, percent)

            # compute placement parameters
            lat_dist = station
            twist = self.twist * percent

            # compute chord
            if self.taper:
                sp_index = spline.binsearch(self.taper.top, lat_dist)
                chord = spline.spline(self.taper.top, taper_y2, sp_index, lat_dist)
            else:
                print "Cannot build a wing with no chord defined!"
                return

            # compute sweep offset pos if a sweep function provided
            if self.sweep:
                sw_index = spline.binsearch(self.sweep.top, lat_dist)
                sweep_dist = spline.spline(self.sweep.top, sweep_y2, sw_index, \
                                               lat_dist)
            else:
                sweep_dist = 0.0

            # make the basic ribs
            label = 'WR' + str(index+1) 
            right_rib = self.make_raw_rib(af, chord, lat_dist, sweep_dist, \
                                              twist, label)
            self.right_ribs.append(right_rib)

            label = 'WL' + str(index+1)
            left_rib = self.make_raw_rib(af, chord, -lat_dist, sweep_dist, \
                                             twist, label)
            self.left_ribs.append(left_rib)

        for rib in self.right_ribs:
            self.make_rib_cuts(rib)
        for rib in self.left_ribs:
            self.make_rib_cuts(rib)

        # lets try cutting out control surfaces here
        for rib in self.right_ribs:
            for flap in self.flaps:
                if self.match_station(flap.start_station, flap.start_station, rib.pos[0]):
                    print "start station = " + str(rib.pos[0])
                elif self.match_station(flap.end_station, flap.end_station, rib.pos[0]):
                    print "end station = " + str(rib.pos[0])
                elif self.match_station(flap.start_station, flap.end_station, rib.pos[0]):
                    print "match flap at mid station " + str(rib.pos[0])
                    rib.contour.trim(side="top", discard="rear", cutpos=flap.pos)
                    rib.contour.trim(side="bottom", discard="rear", cutpos=flap.pos)
        for rib in self.left_ribs:
            for flap in self.flaps:
                if self.match_station(flap.start_station, flap.start_station, rib.pos[0]):
                    print "start station = " + str(rib.pos[0])
                elif self.match_station(flap.end_station, flap.end_station, rib.pos[0]):
                    print "end station = " + str(rib.pos[0])
                elif self.match_station(flap.start_station, flap.end_station, rib.pos[0]):
                    print "left match flap at station " + str(rib.pos[0])
                    rib.contour.trim(side="top", discard="rear", cutpos=flap.pos)
                    rib.contour.trim(side="bottom", discard="rear", cutpos=flap.pos)
            

    def layout_parts_sheets(self, basename, width, height, margin = 0.1):
        l = layout.Layout( basename + '-wing-sheet', width, height, margin )
        for rib in self.right_ribs:
            rib.placed = l.draw_part_cut_line(rib.contour)
        for rib in self.left_ribs:
            rib.placed = l.draw_part_cut_line(rib.contour)
        l.save()

    def layout_parts_templates(self, basename, width, height, margin = 0.1):
        l = layout.Layout( basename + '-wing-template', width, height, margin )
        for rib in self.right_ribs:
            contour = copy.deepcopy(rib.contour)
            contour.rotate(90)
            rib.placed = l.draw_part_demo(contour)
        for rib in self.left_ribs:
            contour = copy.deepcopy(rib.contour)
            contour.rotate(90)
            rib.placed = l.draw_part_demo(contour)
        l.save()

    # make portion from half tip of cutout forward to ideal airfoil
    # nose
    def make_leading_edge1(self, ribs):
        side1 = []
        side2 = []
        for rib in ribs:
            idealfront = rib.contour.saved_bounds[0][0]
            cutbounds = rib.contour.get_bounds()
            cutfront = cutbounds[0][0]
            side1.append( (idealfront+rib.pos[1], -rib.pos[0]) )
            side2.append( (cutfront+rib.pos[1], -rib.pos[0]) )
        side2.reverse()
        shape = side1 + side2
        return shape

    # make portion from tip of rib cutout to rear of diamond
    def make_leading_edge2(self, ribs):
        side1 = []
        side2 = []
        le = self.leading_edge_diamond
        w = math.sqrt(le*le + le*le)
        halfwidth = w * 0.5
        for rib in ribs:
            cutbounds = rib.contour.get_bounds()
            cutfront = cutbounds[0][0]
            side1.append( (cutfront+rib.pos[1], -rib.pos[0]) )
            side2.append( (cutfront+halfwidth+rib.pos[1], -rib.pos[0]) )
        side2.reverse()
        shape = side1 + side2
        return shape

    def make_trailing_edge(self, te, ribs):
        side1 = []
        side2 = []
        for rib in ribs:
            if self.match_station(te.start_station, te.end_station, rib.pos[0]):
                idealtip = rib.contour.saved_bounds[1][0]
                cutbounds = rib.contour.get_bounds()
                cuttip = cutbounds[1][0]
                side1.append( (cuttip+rib.pos[1], -rib.pos[0]) )
                side2.append( (idealtip+rib.pos[1], -rib.pos[0]) )
        side2.reverse()
        shape = side1 + side2
        return shape

    def make_stringer(self, stringer, ribs):
        side1 = []
        side2 = []
        halfwidth = stringer.cutout.xsize * 0.5
        for rib in ribs:
            if self.match_station(stringer.start_station, stringer.end_station, rib.pos[0]):
                xpos = rib.contour.get_xpos(stringer.cutout.cutpos)
                side1.append( (xpos-halfwidth+rib.pos[1], -rib.pos[0]) )
                side2.append( (xpos+halfwidth+rib.pos[1], -rib.pos[0]) )
        side2.reverse()
        shape = side1 + side2
        return shape

    def layout_plans(self, basename, width, height, margin = 0.1, units = "in", dpi = 90):
        sheet = layout.Sheet( basename + '-wing', width, height )
        yoffset = (height - self.span) * 0.5
        #print yoffset

        # determine "x" extent of ribs
        minx = 0
        maxx = 0
        for rib in self.right_ribs:
            sweep_offset = rib.pos[1]
            # print "sweep offset = " + str(sweep_offset)
            bounds = rib.contour.saved_bounds
            if bounds[0][0] + sweep_offset < minx:
                minx = bounds[0][0] + sweep_offset
            if bounds[1][0] + sweep_offset > maxx:
                maxx = bounds[1][0] + sweep_offset
        #print (minx, maxx)
        dx = maxx - minx
        xmargin = (width - 2*dx) / 3.0
        # print "xmargin = " + str(xmargin)

        # right wing
        planoffset = (xmargin - minx, height - yoffset, -1)
        for index, rib in enumerate(self.right_ribs):
            if index == 0:
                nudge = -rib.thickness * 0.5
            elif index == len(self.right_ribs) - 1:
                nudge = rib.thickness * 0.5
            else:
                nudge = 0.0
            rib.placed = sheet.draw_part_top(planoffset, rib.contour, \
                                                 rib.pos, rib.thickness, \
                                                 nudge, "1px", "red")
        shape = self.make_leading_edge1(self.right_ribs)
        sheet.draw_shape(planoffset, shape, "1px", "red")
        shape = self.make_leading_edge2(self.right_ribs)
        sheet.draw_shape(planoffset, shape, "1px", "red")
        for te in self.trailing_edges:
            shape = self.make_trailing_edge(te, self.right_ribs)
            sheet.draw_shape(planoffset, shape, "1px", "red")
        for stringer in self.stringers:
            shape = self.make_stringer(stringer, self.right_ribs)
            sheet.draw_shape(planoffset, shape, "1px", "red")
        for spar in self.spars:
            shape = self.make_stringer(spar, self.right_ribs)
            sheet.draw_shape(planoffset, shape, "1px", "red")

        # left wing
        planoffset = ((width - xmargin) - dx - minx, yoffset, 1)
        for index, rib in enumerate(self.left_ribs):
            if index == 0:
                nudge = rib.thickness * 0.5
            elif index == len(self.left_ribs) - 1:
                nudge = -rib.thickness * 0.5
            else:
                nudge = 0.0
            rib.placed = sheet.draw_part_top(planoffset, rib.contour, \
                                                 rib.pos, rib.thickness, \
                                                 nudge, "1px", "red")
        shape = self.make_leading_edge1(self.left_ribs)
        sheet.draw_shape(planoffset, shape, "1px", "red")
        shape = self.make_leading_edge2(self.left_ribs)
        sheet.draw_shape(planoffset, shape, "1px", "red")
        for te in self.trailing_edges:
            shape = self.make_trailing_edge(te, self.left_ribs)
            sheet.draw_shape(planoffset, shape, "1px", "red")
        for stringer in self.stringers:
            shape = self.make_stringer(stringer, self.left_ribs)
            sheet.draw_shape(planoffset, shape, "1px", "red")
        for spar in self.spars:
            shape = self.make_stringer(spar, self.left_ribs)
            sheet.draw_shape(planoffset, shape, "1px", "red")

        sheet.save()
