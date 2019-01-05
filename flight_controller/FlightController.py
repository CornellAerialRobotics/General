import pigpio
import numpy as np
from flight_controller import *
import time


# represents the flight controller
class FlightController(object):

    # constructor for the flight control
    # initialize proportional gain, integral gain, derivative gain
    # boolean variable to determine if device is armed
    def __init__(self, kp_gain=np.array, ki_gain=np.array, kd_gain=np.array, the_receiver=Receiver,
                 the_imu=IMU, the_motor=Motor):
        self.Kp = kp_gain
        self.Ki = ki_gain
        self.Kd = kd_gain
        self.receiver = the_receiver
        self.imu = the_imu
        self.motor = the_motor
        self.armed = False

        # used for PID updates
        self.error_sum = 0
        self.sys_time = 0
        self.prev_error = 0  # TODO: verify

    # getter for armed status
    @property
    def armed(self):
        return self._armed

    # setter for armed status
    @armed.setter
    def armed(self, armed):
        self._armed = armed

    # getter for proportional gain
    @property
    def Kp(self):
        return self._Kp

    # setter for proportional gain
    @Kp.setter
    def Kp(self, Kp):
        self._Kp = Kp

    # getter for integral gain
    @property
    def Ki(self):
        return self._Ki

    # setter for integral gain
    @Ki.setter
    def Ki(self, Ki):
        self._Ki = Ki

    # getter for derivative gain
    @property
    def Kd(self):
        return self._Kd

    # setter for derivative gain
    @Kd.setter
    def Kd(self, Kd):
        self._Kd = Kd

    # getter for receiver
    @property
    def receiver(self):
        return self._receiver

    # setter for receiver
    @receiver.setter
    def receiver(self, receiver):
        self._receiver = receiver

    # getter for motor
    @property
    def motor(self):
        return self._motor

    # setter for motor
    @motor.setter
    def motor(self, motor):
        self._motor = motor

    # getter for imu
    @property
    def imu(self):
        return self._imu

    # setter for imu
    @imu.setter
    def imu(self, imu):
        self._imu = imu

    # Updates current PID
    def update_PID(self, pi):
        # get delta time
        sys_time_new = pi.get_current_tick()
        dt = (sys_time_new - self.sys_time) / 1e6

        # correct for rollover
        if dt < 0:
            dt = 0
        self.sys_time = sys_time_new

        # Maps control input into angles
        control_angles = Receiver.map_control_input()

        # Get accelerometer and gyroscope data and compute angles
        self.imu.set_accel_data(self.imu.get_updated_accelerometer_data(pi) - self.imu.acc_offsets)
        self.imu.set_gyro_data(self.imu.get_updated_gyroscope_data(pi) - self.imu.gyro_offsets)
        # TODO: see IMU calculate_angles method; possible bug
        self.imu.set_euler_state(self.imu.calculate_angles(pi, dt))

        # Compute errors in pitch and roll and yaw rate
        error = np.array([0 - self.imu.euler_state[0],
                          0 - self.imu.euler_state[1],
                          0])

        # compute error integral
        self.error_sum = self.error_sum + error

        # computer delta error
        delta_error = error - self.prev_error

        # PID law
        if dt > 0:
            u = np.multiply(self.Kp, error) + np.multiply(self.Ki, dt * self.error_sum) + \
                np.multiply(self.Kd, delta_error / dt)
        else:
            u = np.multiply(self.Kp, error) + np.multiply(self.Ki, dt * self.error_sum)

        self.prev_error = error

        # Map controls into vector
        ctrl = np.array([control_angles[3], u[0], u[1], u[2]])

        wm = Motor.map_motor_output(ctrl)

        print(wm)
        Motor.set_motor_pulse(pi, self.motor.MOTOR1, wm[0])
        Motor.set_motor_pulse(pi, self.motor.MOTOR2, wm[1])
        Motor.set_motor_pulse(pi, self.motor.MOTOR3, wm[2])
        Motor.set_motor_pulse(pi, self.motor.MOTOR4, wm[3])

    # run flight loop
    # TODO: break run() into smaller components
    def run(self):
        pi = pigpio.pi()
        print(pi.connected)

        # set receiver input pins
        pi.set_mode(self.receiver.RECEIVER_CH1, pigpio.INPUT)
        pi.set_mode(self.receiver.RECEIVER_CH2, pigpio.INPUT)
        pi.set_mode(self.receiver.RECEIVER_CH3, pigpio.INPUT)
        pi.set_mode(self.receiver.RECEIVER_CH4, pigpio.INPUT)
        pi.set_mode(self.receiver.RECEIVER_CH5, pigpio.INPUT)
        print("Receiver input pins set")

        # initialize callbacks
        cb1 = pi.callback(self.receiver.RECEIVER_CH1, pigpio.EITHER_EDGE, Receiver.cbf1)
        cb2 = pi.callback(self.receiver.RECEIVER_CH2, pigpio.EITHER_EDGE, Receiver.cbf2)
        cb3 = pi.callback(self.receiver.RECEIVER_CH3, pigpio.EITHER_EDGE, Receiver.cbf3)
        cb4 = pi.callback(self.receiver.RECEIVER_CH4, pigpio.EITHER_EDGE, Receiver.cbf4)
        cb5 = pi.callback(self.receiver.RECEIVER_CH5, pigpio.EITHER_EDGE, self.receiver.cbf5)
        print("Callbacks initialized")

        # set motor output pins
        pi.set_mode(self.motor.MOTOR1, pigpio.OUTPUT)
        pi.set_mode(self.motor.MOTOR2, pigpio.OUTPUT)
        pi.set_mode(self.motor.MOTOR3, pigpio.OUTPUT)
        pi.set_mode(self.motor.MOTOR4, pigpio.OUTPUT)
        pi.set_mode(self.motor.MOTOR4, pigpio.OUTPUT)
        print("Motor output pins set")

        # set PWM frequencies
        pi.set_PWM_frequency(self.motor.MOTOR1, 400)
        pi.set_PWM_frequency(self.motor.MOTOR2, 400)
        pi.set_PWM_frequency(self.motor.MOTOR3, 400)
        pi.set_PWM_frequency(self.motor.MOTOR4, 400)
        print("PWM frequency set")

        # setup IMU
        self.imu.setupMPU6050(pi)

        # determine acceleration and gyroscopic offsets
        self.imu.set_acc_offsets(pi)
        self.imu.set_gyro_offsets(pi)

        # machine loop
        while True:
            # Motor.set_motor_pulse(pi, self.motor.MOTOR1, 1)
            # Motor.set_motor_pulse(pi, self.motor.MOTOR2, 1)
            # Motor.set_motor_pulse(pi, self.motor.MOTOR3, 1)
            # Motor.set_motor_pulse(pi, self.motor.MOTOR4, 1)
            # TODO: is this redundant? Does the same thing as self.motor.arm(pi)

            while self.armed is False:
                if self.receiver.ARM is True:
                    # perform pre-flight checks
                    if Receiver.can_arm():
                        self.motor.arm(pi)
                        self.armed = True
                        print("Vehicle is armed")

            # obtains current system time for PID control
            self.sys_time = pi.get_current_tick()

            # flight loop
            while self.receiver.ARM is True:
                # PID loop
                self.update_PID(pi)
