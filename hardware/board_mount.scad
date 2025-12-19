//Base([55,60,3]);
translate([0,0,3]) Posts([51,21]);

module Base(size) {
    cube(size, center = true);
}

module Posts(location) {
    x = location[0]/2;
    y = location[1]/2;
    translate([x,y])
        rotate([0,0,180])
        Post(h = 8, r = 1.5);
    translate([x,-y])
        rotate([0,0,90])
        Post(h = 8, r = 1.5);
    translate([-x,y])
        rotate([0,0,270])
        Post(h = 8, r = 1.5);
    translate([-x,-y])
        rotate([0,0,0])
        Post(h = 8, r = 1.5);
}

module Post(h = 5, r = 1.5) {
    //translate([0,0,h/2])
    difference() {
        cylinder(h = h, r = r, center = true);
        translate([0,0,(h/2)-2])
        cube([r, r, 1.25]);
    }
}