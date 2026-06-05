# OpenVLA Dobot LoRA Example

This subproject is a simple example of LoRA fine-tuning for `openvla/openvla-7b` on a custom Dobot Magician dataset.

It is not full OpenVLA training. The scripts only train small LoRA adapter weights on top of the frozen base model.

It also uses a simplified raw-text action target such as `230.000,40.000,25.000,0.000,1.000`. The official OpenVLA training pipeline uses RLDS datasets and native action tokenization instead.

## Dataset format

Store your training data as a JSON list. Each sample must contain:

- `image`: path to an image file, either absolute or relative to the JSON file
- `instruction`: natural-language robot instruction
- `action`: five values in the format `[x, y, z, r, suction]`

Single-step example:

```json
[
  {
    "image": "images/frame_000001.jpg",
    "instruction": "pick the red cube",
    "action": [230.0, 40.0, 25.0, 0.0, 1.0]
  }
]
```

Multi-step example:

```json
[
  {
    "image": "images/demo_pick_place/frame_000001.jpg",
    "instruction": "pick the red cube and place it in the box",
    "action": [230.0, 40.0, 80.0, 0.0, 0.0]
  },
  {
    "image": "images/demo_pick_place/frame_000002.jpg",
    "instruction": "pick the red cube and place it in the box",
    "action": [230.0, 40.0, 25.0, 0.0, 0.0]
  },
  {
    "image": "images/demo_pick_place/frame_000003.jpg",
    "instruction": "pick the red cube and place it in the box",
    "action": [230.0, 40.0, 25.0, 0.0, 1.0]
  }
]
```

Files included in this folder:

- `dobot_dataset_example.json`: minimal single-step example
- `dobot_trajectory_dataset_example.json`: example of many movement samples from one demonstration
- `trajectory_waypoints_example.json`: example waypoint list for scripted data collection

## Install dependencies

Create and activate a Python environment, then install the requirements:

```bash
pip install -r requirements.txt
```

This installs both the model-training packages and the Dobot recording packages (`pyserial` and `pydobot`).

If model download from Hugging Face requires authentication in your environment, log in first with the Hugging Face CLI or set the appropriate token environment variable.

## Record a multi-step trajectory dataset

Use `record_dobot_trajectory.py` when you want one demonstration to become many training samples.

Waypoint format:

```json
[
  {
    "x": 230.0,
    "y": 40.0,
    "z": 80.0,
    "r": 0.0,
    "suction": 0.0,
    "note": "move above the red cube"
  },
  {
    "x": 230.0,
    "y": 40.0,
    "z": 25.0,
    "r": 0.0,
    "suction": 1.0,
    "note": "pick the cube"
  }
]
```
Note: use the code in the ```mapping``` folder to translate camera to dobot coordinates


How the recorder works:

1. Capture the current camera frame.
2. Save that frame as one dataset sample.
3. Store the next waypoint action as the target `[x, y, z, r, suction]`.
4. If `--move-robot` is enabled, execute that waypoint on the Dobot.

This means every sample is: observation now -> action next.

Example command:

```bash
python record_dobot_trajectory.py \
  --instruction "pick the red cube and place it in the box" \
  --waypoints trajectory_waypoints_example.json \
  --dataset dobot_trajectory_dataset.json \
  --demo-name demo_pick_place \
  --move-robot
```

What this creates:

- images under `images/demo_pick_place/`
- dataset entries appended to `dobot_trajectory_dataset.json`

Recommended collection workflow:

1. Put the robot and object in a known start state.
2. Prepare a waypoint list for one task demonstration.
3. Run the recorder once for that demonstration.
4. Change object positions, clutter, or lighting.
5. Record the same task again as `demo_002`, `demo_003`, and so on.
6. Keep appending to the same dataset JSON file.

Good starting scale:

- 20 demos x 20 steps = about 400 samples
- 50 demos x 30 steps = about 1500 samples

In practice, more scene variation usually helps more than repeating the exact same trajectory.

## Run training

The training script expects a CUDA-capable GPU. CPU training is not supported in this scaffold.

From the `openvla_dobot/` folder:

```bash
python train_openvla_lora.py \
  --dataset dobot_dataset_example.json \
  --output-dir openvla_dobot_lora \
  --epochs 1 \
  --batch-size 1 \
  --grad-accumulation-steps 8 \
  --learning-rate 5e-5
```

Notes:

- The script loads `openvla/openvla-7b` with `trust_remote_code=True`.
- LoRA is applied to `q_proj`, `k_proj`, `v_proj`, and `o_proj`.
- The saved output directory contains the adapter weights and PEFT metadata, not a fully merged base model checkpoint.

## Train on a trajectory dataset

You do not need a separate trainer for many movement samples. The same `train_openvla_lora.py` script already works with a larger JSON file containing many per-step entries.

Example command for a recorded trajectory dataset:

```bash
python train_openvla_lora.py \
  --dataset dobot_trajectory_dataset.json \
  --output-dir openvla_dobot_lora \
  --epochs 3 \
  --batch-size 1 \
  --grad-accumulation-steps 16 \
  --learning-rate 2e-5
```

Suggested training workflow:

1. Start with one short recorded demo.
2. Open the dataset JSON and confirm the image paths and actions look correct.
3. Record multiple demos of the same task from different object positions.
4. Run one short training pass first.
5. Increase to 3 to 5 epochs only after the first run succeeds.
6. Test on held-out frames that were not used during training.

Practical tips:

- Keep the instruction text consistent while building the first dataset.
- Use small step-to-step changes in the trajectory so each action is easy to imitate.
- If prompts get longer, raise `--max-text-length`.
- If you run out of GPU memory, keep `--batch-size 1` and increase `--grad-accumulation-steps`.
- If training is unstable, reduce `--learning-rate` to `1e-5` or `2e-5`.

## Run inference

After training, run inference with the base OpenVLA model plus the saved adapter:

```bash
python infer_openvla_dobot.py \
  --image images/frame_000001.jpg \
  --instruction "pick the red cube" \
  --adapter openvla_dobot_lora
```

The script prints:

- the raw generated action text
- the parsed action list `[x, y, z, r, suction]`

For multi-step robot behavior, you would normally run inference in a loop:

1. capture current frame
2. predict next action
3. execute that action safely
4. capture the next frame
5. repeat until the task is complete

This repository does not yet include a closed-loop autonomous execution script. It includes the training scaffold, the inference script, and the trajectory recorder.

## Safety warning

Do not send model outputs directly to a real robot without safety checks.

At minimum, apply:

- workspace limits for `x`, `y`, `z`, and `r`
- clamping or validation for the suction command
- collision checks
- human review before execution

This example is a training and inference scaffold, not a safe robot control stack.
