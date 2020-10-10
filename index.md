---
layout: default
---

[Silizium Labor Bonn](https://github.com/SiLab-Bonn)


( Last modified: {{ site.time | date: '%B %d, %Y' }} )
<h1> Proton Irradiation Site for Silicon Detectors at Bonn University </h1>
A newly-installed proton irradiation site at the [Bonn isochronous cyclotron](https://www.zyklotron.hiskp.uni-bonn.de/zyklo_e/index.html) at the [Helmholtz Institut für Strahlen- und Kernphysik (HISKP)](https://www.hiskp.uni-bonn.de/) allows radiation damage studies of prototype silicon detectors for state-of-the-art, high-energy physics experiments such as [**ATLAS**](https://atlas.cern/) and [**BELLE 2**](https://www.belle2.org/). Especially pixel detectors are positioned close to the interaction point due to their high spatial resolution and tracking capabilities. Therefore, they are exposed to a harsh radiation environment which dictates their lifetime. In order to verify that the detectors meet requirements, radiation damage studies are necessary for prototype detector concepts.



<h3> Setup </h3>
<figure>
  <img src="figures/Radiation_1.jpg" width="300">
  <img src="figures/Radiation_2.jpg" width="300">
  <figcaption>Overview of the irradiation site at the high current room of the Bonn isochronus cyclotron. The setup consists of an insulated cooling box on a two-dimensional motor stage which is
mounted on a custom-made setup table. A liquid nitrogen reservoir is used to cool nitrogen gas which is guided into the
cooling box.Shown is  the setup in irradiation position, only several centimeters from the extraction
window.</figcaption>
</figure>

<h3> Beam Diagnostic</h3>
<img src="figures/aufbau.png" width="500">


[//]: <> In order to determine the beam current and position in the xy-plane non-destructively, a 4-channel secondary electron monitor (SEM) is used.
In front of the extraction the Beam penetrates a 4-channel secondary electron monitor. The penetration is directly proportional to the beam current. So it is possible to determine the beam current and position in the xy-plane non-destructively.
After the SEM the Beam goes through a Beam-loss-monitor, which is based on a faraday cup. Through this it is possible to determine the exact beam extraction current, if the beam is displaced.
The beam goes then though an exit window and encounters the device.

<figure>
  <img src="figures/beam_current.png" width="300">
  <img src="figures/position.png" width="300">
  <figcaption> Shown are the Visualizations of beam data, available in the online monitor tab of the irrad_control GUI using the installed  SEM. The first figure shows the beam current over time while the no beam is extracted. The second figure shows the relative beam position at the location of the SEM.
</figcaption>
</figure>


<h3> Irradiation Characteristics </h3>

|         |
| :------- | :------- |
| Energies| 7 to 14 MeV per nucleon|
|Ions|Proton to Oxygen|
|Beam intensity internal / external | max. 10 µA|

<h3> Fluence Estimation </h3>
The proton fluece <img src="https://latex.codecogs.com/svg.latex?\Large&space; \Phi_\text{P}" /> is directly proportional to the NIEL damage. Knowing the proton beam current <img src="https://latex.codecogs.com/svg.latex?\Large&space; I_\text{P}" />, the fluence is calculated by
<p>
<img src="https://latex.codecogs.com/svg.latex?\Large&space; \Phi_\text{P}=\frac{I_\text{P}}{q_\text{e}\cdot v_\text{x}\cdot \Delta y}" />
<p>
This equation describes the fluence per complete scan of the respective area, with <img src="https://latex.codecogs.com/svg.latex?\Large&space; q_\text{e}" /> the electric charge, <img src="https://latex.codecogs.com/svg.latex?\Large&space; v_\text{x}" />, the scan speed and <img src="https://latex.codecogs.com/svg.latex?\Large&space; \Delta y" /> the step size.


<figure>
  <img src="figures/xy_stage.png" width="300">
</figure>
Shown is the the schematic scanning procedure, the beam spot (red circle) is moved in a grid over the scanned  area
, separated into H/∆y rows. The DUT  is placed inside the green
rectangle, where the scan speed is constant.
<figure>
  <img src="figures/fluence.png" width="500">
</figure>
Histogram of the fluence per scanned row of one set of irradiated diodes. The proton
fluence is indicated on the first, the neutron fluence  on the second y-axis. The
mean fluence over the entire scan area is given by the horizontal line.

<figure>
  <img src="figures/kappa_BONN.png" width="500">
</figure>
For our 14 MeV protons we determined a hardness factor of 4.1 ±0.6. The blue curve shows the std. deviation of 5 test structures within the same fluence.





