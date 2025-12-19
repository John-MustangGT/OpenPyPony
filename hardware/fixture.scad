
difference() {
    //cube([60, 60, 3], center=true);
    //baseplate();
    roundedcube_corners([60,60,3], center=true, radius = 1.0);
    translate([0, -13, 0])
        cutout2(thickness=4);
    translate([0, +13, 0])
        cutout2(thickness=4);
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
module cutout2(size=[51,21], thickness=2.0, corner=1.0, offset=[1,1]) {
    xoff = (size[0]/2)-(corner/2);
    yoff = (size[1]/2)-(corner/2);
    thickoff = thickness/2;
    union() {
        roundedcube_corners(size=[size[0]-offset[0],size[1]-offset[1], thickness], center=true);
        translate([0,0,thickoff])
            roundedcube_corners(size=[size[0],size[1], thickness], center=true);
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
    