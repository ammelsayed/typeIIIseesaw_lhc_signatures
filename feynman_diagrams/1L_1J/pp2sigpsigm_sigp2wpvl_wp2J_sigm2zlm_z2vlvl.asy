import feynman;

currentpen = linewidth(0.75);
fmdefaults();

real L = 50;

pair zl = (-0.75*L, 0);
pair zr = (+0.75*L, 0);

pair xu = zl + L*dir(120);
pair xl = zl + L*dir(-120);

pair yu = zr + L*dir(60);
pair yl = zr + L*dir(-60);

pair a = yu + L*dir(60);
pair b = yu + 1.5*L;

pair c = b + L*dir(30);
pair d = b + L*dir(-30);

pair a2 = yl + L*dir(-60);
pair b2 = yl + 1.5*L;

pair c2 = b2 + L*dir(30);
pair d2 = b2 + L*dir(-30);

// production
drawFermion(zl--xu);
drawFermion(xl--zl);
drawPhoton(zl--zr);

// heavy leptons
drawFermion(zr--yu);
drawFermion(zr--yl);

// sigp decay
drawFermion(yu--a);
drawPhoton(yu--b);
drawFermion(b--c);
drawFermion(b--d);

// sigm decay
drawFermion(yl--a2);
drawPhoton(yl--b2);
drawFermion(b2--c2);
drawFermion(b2--d2);

dot(zl, linewidth(3));
dot(zr, linewidth(3));
dot(yu, linewidth(3));
dot(yl, linewidth(3));
dot(b, linewidth(3));
dot(b2, linewidth(3));

label("$\bar{q}$", xu, left);
label("$q$", xl, left);

label("$\gamma^*/Z^*$", zl--zr, up);

label("$N^+$", zr--yu, left);
label("$N^-$", zr--yl, left);

label("$\nu$", a, right);
label("$W^+$", yu--b, down);

label("$q$", c, right);
label("$\bar{q}'$", d, right);

label("$\ell^-$", a2, right);
label("$Z$", yl--b2, up);

label("$\nu$", c2, right);
label("$\bar{\nu}$", d2, right);
