//mount for TGM336h

// board:   13.60 x 16.40
// antenna: 18.80mm x 6.00 mm x 6.40 mm(thick)/4.70

BASE  = [30.00, 35.00, 4.50];
ATGM  = [13.90, 16.70, 2.0];
ANT   = [19.80,  7.00, 4.7];
Mount = [12.0, 15.0, 2.0]; 

difference() {
    // Bracket
    union() {
        roundedcube_corners(size = BASE, center = true, radius = 1.0);
        // Pins
//        translate([11,0,+2]) cylinder(h=3, r=1.5, center = true);
//        translate([-11,0,+2]) cylinder(h=3, r=1.5, center = true);
    }
    //ATGM
    translate([0, 5, 0]) union() {
        cube(size = ATGM+[0,0,5], center = true);
//        translate([0,0,+2])
//        cube(size = ATGM + [0,0,1], center = true);
    }
    //Antenna
    translate([0, -9, 0]) union() {
        cube(size = ANT, center = true);
    }
    //Mount Holes
    translate([Mount[0],Mount[1],0]) cylinder(h=5, r=Mount[2], center = true);
    translate([-Mount[0],Mount[1],0]) cylinder(h=5, r=Mount[2], center = true);
    translate([Mount[0],-Mount[1],0]) cylinder(h=5, r=Mount[2], center = true);
    translate([-Mount[0],-Mount[1],0]) cylinder(h=5, r=Mount[2], center = true);
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