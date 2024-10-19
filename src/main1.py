"""
This example commands multiple servos connected to a pi3hat.  It
uses the .cycle() method in order to optimally use the pi3hat
bandwidth.
"""

import asyncio
import math
import moteus
import moteus_pi3hat
import time

import numpy as np
import pydrake.all as drake

class Arm:
    def __init__(self, m1, m2, l1, l2, initial_end_mass):
        """Initialize the 2-DOF arm with initial parameters."""
        self.m1 = m1
        self.m2 = m2
        self.l1 = l1
        self.l2 = l2
        
        # Create the multibody plant
        self.plant = drake.multibody.plant.MultibodyPlant(time_step=0.0)
        
        # Create links
        self.link1 = self.plant.AddRigidBody(
            "link1",
            drake.SpatialInertia(
                mass=m1,
                p_PScm_E=np.array([l1/2, 0, 0]),
                G_SP_E=drake.RotationalInertia(m1*l1**2/12, m1*l1**2/12, m1*l1**2/12)
            )
        )
        
        # For link2, use a parameter that can be updated (assistance from exoskeleton)
        self.link2 = self.plant.AddRigidBody("link2", drake.SpatialInertia())
        self.end_mass_param = self.plant.AddParameter(
            drake.multibody.Parameter(1)  # 1-dimensional parameter
        )
        
        # Add joints
        self.shoulder = self.plant.AddRevoluteJoint(
            "shoulder",
            self.plant.world_frame(),
            self.link1.body_frame(),
            [0, 0, 1]
        )
        self.elbow = self.plant.AddRevoluteJoint(
            "elbow",
            self.link1.body_frame(),
            self.link2.body_frame(),
            [0, 0, 1]
        )
        
        # Add gravity
        self.plant.mutable_gravity_field().set_gravity_vector([0, -9.81, 0])
        
        # Finalize the plant
        self.plant.Finalize()
        
        # Create a context for the plant
        self.context = self.plant.CreateDefaultContext()
        
        # Set the initial end mass
        self.set_end_mass(initial_end_mass)

    def set_end_mass(self, end_mass):
        """Update the end mass and recalculate link2 properties."""
        total_mass2 = self.m2 + end_mass
        com2 = (self.m2 * self.l2/2 + end_mass * self.l2) / total_mass2
        I2 = self.m2 * (self.l2/2)**2 + end_mass * self.l2**2  # Simple approximation

        # Update the parameter value
        self.plant.SetParameter(self.context, self.end_mass_param, [end_mass])
        
        # Update link2 spatial inertia
        M2 = drake.SpatialInertia(
            mass=total_mass2,
            p_PScm_E=np.array([com2, 0, 0]),
            G_SP_E=drake.RotationalInertia(I2, I2, I2)
        )
        self.plant.SetBodySpatialInertiaInBodyFrame(self.context, self.link2, M2)

    def calculate_inverse_dynamics(self, q, v, vd):
        """Calculate inverse dynamics using current end mass."""
        # Set the state
        self.plant.SetPositions(self.context, q)
        self.plant.SetVelocities(self.context, v)
        
        # Calculate inverse dynamics
        return self.plant.CalcInverseDynamics(
            self.context, vd, drake.multibody.plant.MultibodyForces(self.plant)
        )

async def main():
    # We will be assuming a system where there are 4 servos, each
    # attached to a separate pi3hat bus.  The servo_bus_map argument
    # describes which IDs are found on which bus.
    transport = moteus_pi3hat.Pi3HatRouter(
        servo_bus_map = {
            1:[1, 2] # ,
            # 2:[22]
        },
    )

    # We create one 'moteus.Controller' instance for each servo.  It
    # is not strictly required to pass a 'transport' since we do not
    # intend to use any 'set_*' methods, but it doesn't hurt.
    #
    # This syntax is a python "dictionary comprehension":
    # https://docs.python.org/3/tutorial/datastructures.html#dictionaries
    servos = {
        servo_id : moteus.Controller(id=servo_id, transport=transport)
        for servo_id in [1, 2]
    }

    # We will start by sending a 'stop' to all servos, in the event
    # that any had a fault.
    await transport.cycle([x.make_stop() for x in servos.values()])

    while True:
        # The 'cycle' method accepts a list of commands, each of which
        # is created by calling one of the `make_foo` methods on
        # Controller.  The most common thing will be the
        # `make_position` method.

        now = time.time()

        # For now, we will just construct a position command for each
        # of the 4 servos, each of which consists of a sinusoidal
        # velocity command starting from wherever the servo was at to
        # begin with.
        #
        # 'make_position' accepts optional keyword arguments that
        # correspond to each of the available position mode registers
        # in the moteus reference manual.
        commands = [
            servos[1].make_position(
                feedforward_torque=0,
                position=math.nan,
                velocity=0.1*math.sin(now),
                query=True),
            servos[2].make_position(
                position=math.nan,
                velocity=0.1*math.sin(now + 1),
                query=True),
        ]

        # By sending all commands to the transport in one go, the
        # pi3hat can send out commands and retrieve responses
        # simultaneously from all ports.  It can also pipeline
        # commands and responses for multiple servos on the same bus.
        results = await transport.cycle(commands)

        # The result is a list of 'moteus.Result' types, each of which
        # identifies the servo it came from, and has a 'values' field
        # that allows access to individual register results.
        #
        # Note: It is possible to not receive responses from all
        # servos for which a query was requested.
        #
        # Here, we'll just print the ID, position, and velocity of
        # each servo for which a reply was returned.

        q = results.values[moteus.Register.POSITION]
        v = moteus.Register.VELOCITY
        vd = 0

        print(", ".join(
            f"({result.arbitration_id} " +
            f"{result.values[moteus.Register.POSITION]} " +
            f"{result.values[moteus.Register.VELOCITY]})"
            for result in results))

        # We will wait 20ms between cycles.  By default, each servo
        # has a watchdog timeout, where if no CAN command is received
        # for 100ms the controller will enter a latched fault state.
        await asyncio.sleep(0.02)

if __name__ == '__main__':
    asyncio.run(main())