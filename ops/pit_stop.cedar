// Pit Stop leash for the race engineer (ops/race_engineer.py).
// Each harness tool is a Cedar action; context.input carries the tool arguments and
// context.session carries hour_utc, call_count and anything the enricher adds.
// Reads are free. Writes to the car are forbidden unless the operator has confirmed
// this session (DEEPRACER_OPERATOR_CONFIRMED=1 sets context.session.operator_confirmed).

// Reading is always allowed.
permit(principal, action == Action::"read", resource);
permit(principal, action == Action::"web_fetch", resource);

// The engineer's own notebook: memory and context recall, task notes. Nothing here touches the car.
permit(principal, action in [Action::"search_memory", Action::"retrieve_context", Action::"todo_write"], resource);

// Shell: allowed, but the forbids below carve out everything that changes the car.
permit(principal, action == Action::"shell", resource);

// Motion topics are never the engineer's business, confirmed or not.
forbid(principal, action == Action::"shell", resource)
when {
  context.input.command like "*manual_drive*" ||
  context.input.command like "*cmd_vel*" ||
  context.input.command like "*servo_msg*"
};

// Service restarts, package changes, reboots and sysfs writes need a confirmed operator.
forbid(principal, action == Action::"shell", resource)
when {
  (context.input.command like "*systemctl restart*" ||
   context.input.command like "*systemctl stop*" ||
   context.input.command like "*apt*" ||
   context.input.command like "*reboot*" ||
   context.input.command like "*shutdown*" ||
   context.input.command like "*> /sys/*" ||
   context.input.command like "*rm -*")
  && !(context.session has operator_confirmed && context.session.operator_confirmed == true)
};

// Editing files on the car (calibration, launch files) needs a confirmed operator.
permit(principal, action in [Action::"write", Action::"edit"], resource);
forbid(principal, action in [Action::"write", Action::"edit"], resource)
unless {
  context.session has operator_confirmed && context.session.operator_confirmed == true
};
