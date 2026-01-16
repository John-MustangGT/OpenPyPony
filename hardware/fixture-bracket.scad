
function inch(i) = 25.4 * i;

GPS=[14.5, 16.6, 0.08];

union() {
    // Base
    translate([0, 5, 0])
    cube(inch([2.5,3.8,0.05]), center=true);
    
    // PAD1010D GPS
    translate(inch([0.55,0,0])) {
        rotate([0,0,0])
        pillar(size=inch([1.0,1.0,0.1]));
        raisedText(msg="GPS");
    }
    
    // ICM20948 Accel, Gyro, Mag
    translate(inch([-0.55,0.0,0])) {
        rotate([0,0,90])
        pillar(size=inch([1.0,0.8,0.1]));
        raisedText(msg="Accel");
    }
    
    // ESP-01 Mount
    translate([0,-28,0]) {
        pillar(size=[42.0,24.0,2.0]);
        raisedText(msg="ESP-01");
    }
    
    // SD Card Mount
    translate([15,32,0]) {
        pillar(size=[28.0, 30.0 ,2.0]);
        raisedText(msg="SD Card");
    }
    
    // USB C
    translate([-23,27,0]) {
        pillar(size=[13.0, 22.0 ,2.0]);
        raisedText(msg="USB-C");
    } 
}

module raisedText(msg = "Text", size = 3) {
    linear_extrude(height = 1.5)
    text(msg, size = size, font = "Arial");
}

module pillar(size=[15,18,2], thickness=[2.0,2.0,3.0]) {
    size_x = size[0]; size_y = size[1]; size_z = size[2];
    thick_x = thickness[0]; thick_y = thickness[1]; thick_z = thickness[2];
    
    translate([0,0,(size_z+thick_z)/2])
    difference() {
        roundedcube_corners(size=size+thickness, center=true);
        
        translate([0,0,1.1]) 
        linear_extrude(height=thick_z*2+1, center=true, scale=1.1) 
        square([size_x+2*thick_x, size_y-3*thick_y], center=true);
        
        translate([0,0,1.1])
        linear_extrude(height=thick_z*2+1, center=true, scale=1.1) 
        square([size_x-3*thick_x, size_y+2*thick_y], center=true);
        
        translate([0,0,3])
        cube(size+[0,0,1], center=true);
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
 
module pin(loc=[0,0,0], h=3, r=2) {
    translate(loc) difference(){
        cylinder(h=h, r=r+0.5, center=false);
        cylinder(h=h+0.5, r=r-0.5, center=false);
    }
}
