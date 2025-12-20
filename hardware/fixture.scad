PLATE=[60,93,3];
PICO=[51,21];
PICOloc=[0, -12, 0];
COWBELL=PICO;
COWBELLloc=[0, +12, 0];
GPS=[15.7,13.1];
GPSloc=[-16, +32, 0];
ACC=[25.4,17.8];
ACCloc=[-12, -35, 0];
PIN1=[5,2];
PIN1loc=[0,35,0];
PIN2=PIN1;
PIN1loc=[10,-35,0];

//Bottom plate
translate([70,0,0]) {
    union() {
        difference() {
            roundedcube_corners([60,93,3], center=true, radius = 1.0);
            // Raspberry Pi Pico 2w
            translate([0, -12, 0])
                cutout2(size=[51,21], thickness=4);
            // Adafruit Picowbell Adatalogger
            translate([0, +12, 0])
                cutout2(size=[51,21], thickness=4);
            // Teyleten ATGM336H GPS
            translate([-16, +32, 0])
                cutout2(size=[15.7,13.1], thickness=4); 
            // Adafruit LIS3DH STEMMA Breakout
            translate([-12, -35, 0])
                cutout2(size=[25.4,17.8], thickness=4);
        }
        translate([0,35,0]) cylinder(h=5, r=2, center=false);
        translate([10,-35,0]) cylinder(h=5, r=2, center=false);
    }
}

//Top plate
translate([0,0,0]) {
    difference() {
        roundedcube_corners([60,93,3], center=true, radius = 1.0);
        // Raspberry Pi Pico 2w
        translate([0, -12, 0])
            cutout2(size=[51,21], thickness=4, flat=true);
        // Adafruit Picowbell Adatalogger
        translate([0, +12, 0])
            cutout2(size=[51,21], thickness=4, flat=true);
        // Teyleten ATGM336H GPS
        translate([-16, +32, 0])
            cutout2(size=[15.7,13.1], thickness=4, flat=true); 
        // Adafruit LIS3DH STEMMA Breakout
        translate([-12, -35, 0])
            cutout2(size=[25.4,17.8], thickness=4, flat=true);
        translate([0,35,-1]) cylinder(h=5, r=2, center=false);
        translate([10,-35,-1]) cylinder(h=5, r=2, center=false);
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
    