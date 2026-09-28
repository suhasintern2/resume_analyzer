# Application Startup Optimization

## Problem
The Resume Analyzer application backend was experiencing slow startup times due to:
1. Synchronous startup recovery process that runs on every boot
2. Immediate initialization of background worker and associated services

## Solution
Added a new configuration option `SKIP_STARTUP_RECOVERY` that allows skipping the synchronous crash recovery process during application startup.

## Configuration

To enable faster startup times, set the following environment variable:

```bash
SKIP_STARTUP_RECOVERY=true
```

This can be added to your `.env` file or exported in your shell environment.

### Example .env file:
```bash
APP_ENV=development
LLM_PROVIDER=groq
LLM_API_KEY=your_key_here
# ... other settings ...
SKIP_STARTUP_RECOVERY=true
```

## How It Works

When `SKIP_STARTUP_RECOVERY=true` is set:
1. The application skips the synchronous startup recovery process
2. The background worker still starts normally if `WORKER_ENABLED=true` (default)
3. Application becomes available to accept connections much faster

### When to Use This
- **Development**: For faster iteration cycles
- **Testing**: When running test suites
- **CI/CD**: For faster pipeline execution
- **Any scenario** where startup speed is more important than automatic crash recovery

### When NOT to Use This
- **Production environments**: Where automatic recovery from crashes is important
- **High-availability setups**: Where you want the app to self-heal after crashes

## Technical Details

The startup recovery process (found in `app/services/worker.py::run_startup_recovery()`) performs the following:
- Checks for interviews left in `PROCESSING`, `ANSWER_UPLOADED` with processing stage, or `EVALUATING` with processing stage states
- Resets these interviews back to a claimable state so they can be retried
- This recovery is important for handling application crashes that leave interviews in intermediate states

By skipping this process, you're trading off automatic crash recovery for faster startup times. Interviews that were interrupted by a previous crash will need to be handled manually or will remain in their failed state.

## Related Configuration

The background worker can still be controlled independently via:
```bash
WORKER_ENABLED=false  # To disable the background worker entirely
```

For maximum startup speed in development, you might use:
```bash
WORKER_ENABLED=false
SKIP_STARTUP_RECOVERY=true
```

## Verification

To verify that startup recovery is being skipped, look for this log message during application startup:
```
INFO:     __main__: Skipping startup recovery for faster startup
```

If you don't see this message and `SKIP_STARTUP_RECOVERY=true` is set, double-check that:
1. The environment variable is properly set
2. The application is picking up the updated configuration
3. There are no typos in the variable name