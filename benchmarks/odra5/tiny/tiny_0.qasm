OPENQASM 2.0;
include "qelib1.inc";
qreg q[5];
h q[3];
rz(0.254241894975283) q[4];
cx q[2],q[3];
cx q[1],q[4];
cx q[0],q[2];