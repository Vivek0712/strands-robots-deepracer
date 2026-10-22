# Contrarian

**The framing is the first flaw.** "Exercise five pillars" is a vendor checklist, not a demo. Any plan graded on pillar coverage produces exactly the failure the framing warns about: five disconnected gimmicks. Drop the coverage requirement. Pick one idea ("the robot refuses, and tells you why") and let pillars appear only where they carry that idea.

**The pool's fatal assumption is motion.** A third of the candidates (U02, U04B, U05, U09, U16, U23, U24) are closed-loop driving on a car with no odometry, no pose, no watchdog, and a 3-6 s VLM round trip over venue uplink. The on-car deadman node does not exist yet. Until it is written, flashed and tested with the router yanked, nothing in this plan may move. If it is not done by end of week one, the showcase is zero-motion. Full stop.

**The unnamed single point of failure is the cloud.** Nova Pro, Nova Sonic and the harness all need internet. The travel router isolates the rover, not Bedrock. The decider is the only pillar that runs locally. Design the demo so that with internet dead, the decider plus the gate plus a text console still produce a complete show.

**Traps:** U16 (RL model, flaky mode flip, drives into feet); U18 live (a bad calibration write kills the day); U10 with a second physical robot; U06 (mis-transcribed name recalled to a stranger is a privacy incident on stage); U14/U21 open mic in hall noise. U09 is a toy.

**What I would build:** U22 opener, U17 as the only motion, U13 and U11 as refusals, U07 as the payoff. That is four beats, one story, every stop measurable. Pit Stop and Two Bodies as pre-recorded 60 s cuts, labelled as such. Bidi push-to-talk only. Box is a slide. Four weeks solo buys one reliable thing, not eleven. Rehearse the failure modes, not the happy path.
