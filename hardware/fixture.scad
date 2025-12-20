PLATE=[60,110,3];
PICO=[51,21];
PICOloc=[0, -12, 0];
COWBELL=PICO;
COWBELLloc=[0, +12, 0];
GPS=[13.1,15.7];
GPSloc=[18, -35, 0];
ACC=[25.4,17.8];
ACCloc=[-12, -35, 0];
ESP=[41.7, 24.5];
ESPloc=[0, +38, 0];
PIN1=[5,2];
PIN1loc=[-25,35,0];
PIN2=PIN1;
PIN2loc=[6,-35,0];
PIN3=PIN1;
PIN3loc=[25,35,0];
smidge=0.1;
font_size = 5;
text_height = 2;

//Bottom plate
translate([70,0,0]) {
    union() {
        difference() {
            roundedcube_corners(PLATE, center=true, radius = 1.0);
            // Raspberry Pi Pico 2w
            translate(PICOloc)
                cutout2(size=PICO, thickness=4);
            // Adafruit Picowbell Adatalogger
            translate(COWBELLloc)
                cutout2(size=COWBELL, thickness=4);
            // Teyleten ATGM336H GPS
            translate(GPSloc)
                cutout2(size=GPS, thickness=4); 
            // Adafruit LIS3DH STEMMA Breakout
            translate(ACCloc)
                cutout2(size=ACC, thickness=4);
             // Geekstory ESP=01 Breakout
            translate(ESPloc)
                cutout2(size=ESP, thickness=4);
        }
        translate(PIN1loc) cylinder(h=PIN1[0], r=PIN1[1], center=false);
        translate(PIN2loc) cylinder(h=PIN2[0], r=PIN2[1], center=false);
        translate(PIN3loc) cylinder(h=PIN3[0], r=PIN3[1], center=false);
    }
}

//Top plate
translate([0,0,0]) {
    difference() {
        roundedcube_corners(PLATE+[0,0,-0.75], center=true, radius = 1.0);
        // Raspberry Pi Pico 2w
        translate(PICOloc)
            cutout2(size=PICO, thickness=4, flat=true);
        // Adafruit Picowbell Adatalogger
        translate(COWBELLloc)
            cutout2(size=COWBELL, thickness=4, flat=true);
        // Teyleten ATGM336H GPS
        translate(GPSloc)
            cutout2(size=GPS, thickness=4, flat=true); 
        // Adafruit LIS3DH STEMMA Breakout
        translate(ACCloc)
            cutout2(size=ACC, thickness=4, flat=true);
        // Geekstory ESP=01 Breakout
        translate(ESPloc)
            cutout2(size=ESP, thickness=4, flat=true);
        translate(PIN1loc+[0,0,-1]) cylinder(h=PIN1[0], r=PIN1[1]+smidge, center=false);
        translate(PIN2loc+[0,0,-1]) cylinder(h=PIN2[0], r=PIN2[1]+smidge, center=false);
        translate(PIN3loc+[0,0,-1]) cylinder(h=PIN3[0], r=PIN3[1]+smidge, center=false);
    }
    translate([0,(-PLATE[1]/2)+7,0])
    linear_extrude(height = text_height) {
        text("OpenPonyLogger", size = font_size, halign="center", valign="center");
        translate([8,-5,0])
        text("Copywrite John Orthoefer 2025", size=2, halign="center", valign="center");
    }
}

module roundedcube_corners(size = [1, 1, 1], center = false, radius = 0.5) {
    // If single value, convert to [x, y, z] vector
    size = (size[0] == undef) ? [size, size, size] : size;

    translate = (center == false) ?
        [radius, radius, radius] :
        [
            radius - (size[0] / 2),
            radius - (size[1] / 2),
            radius - (size[2] / 2)
    ];

    translate(v = translate)
    minkowski() {
        cube(size = [
            size[0] - (radius * 2),
            size[1] - (radius * 2),
            size[2] - (radius * 2)
        ]);
        cylinder(r = radius);
    }
}
module cutout2(size=[51,21], thickness=2.0, corner=1.0, offset=[1,1], flat=false) {
    xoff = (size[0]/2)-(corner/2);
    yoff = (size[1]/2)-(corner/2);
    thickoff = thickness/2;
    union() {
        roundedcube_corners(size=[size[0]-offset[0],size[1]-offset[1], thickness], center=true);
        if (!flat) {
        translate([0,0,thickoff])
            roundedcube_corners(size=[size[0],size[1], thickness], center=true);
        }
    }
}
    
module cutout(size=[51,21], thickness=2.0, corner=1.0, offset=[1,1]) {
    xoff = (size[0]/2)-(corner/2);
    yoff = (size[1]/2)-(corner/2);
    thickoff = thickness/2;
    union() {
        cube(size=[size[0]-offset[0],size[1]-offset[1], thickness], center=true);
        translate([0,0,thickoff])
            cube(size=[size[0],size[1], thickness], center=true);
        translate([xoff, yoff, thickoff])
            cylinder(h=thickness, r=corner, center=true);
        translate([-xoff, yoff, thickoff])
            cylinder(h=thickness, r=corner, center=true);
        translate([xoff, -yoff, thickoff])
            cylinder(h=thickness, r=corner, center=true);
        translate([-xoff, -yoff, thickoff])
            cylinder(h=thickness, r=corner, center=true);
    }
}
    