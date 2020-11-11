"""Experiment comparing training performance of GLUE finetuning task with differing hardware.

This script prepares the `code/train/transformers/glue/train.py` script using
different compute clusters. The idea of this experiment is to compare training
times between different VM SKUs.

To run this script you need:

    - An Azure ML Workspace
    - A ComputeTarget to train on (we recommend a GPU-based compute cluster)
    - Azure ML Environment:
        - create the required python environment by running the `aml_utils.py` script
        - This registers two environments "transformers-datasets-cpu" and "transformers-datasets-gpu"

Note:
    
    Arguments passed to `train.py` will override TrainingArguments:
    
    https://huggingface.co/transformers/main_classes/trainer.html#trainingarguments

"""
from pathlib import Path
from azureml.core import Workspace  # connect to workspace
from azureml.core import Experiment  # connect/create experiments
from azureml.core import Environment  # manage e.g. Python environments
from azureml.core import ScriptRunConfig  # prepare code, an run configuration
from azureml.core import Run  # used for type hints


def submit_aml_run(
    workspace: Workspace,
    target_name: str,
    experiment_name: str,
    environment: Environment,
    glue_task: str,
    model_checkpoint: str,
) -> Run:

    # get compute target
    target = workspace.compute_targets[target_name]

    # get/create experiment
    exp = Experiment(workspace, experiment_name)

    # set up script run configuration
    config = ScriptRunConfig(
        source_directory="src",
        script="run_glue.py",
        arguments=[
            "--output_dir", "outputs",
            "--task", glue_task,
            "--model_checkpoint", model_checkpoint,

            # training args
            "--evaluation_strategy", "steps",
            "--eval_steps", 200,
            "--learning_rate", 2e-5,
            "--per_device_train_batch_size", 16,
            "--per_device_eval_batch_size", 16,
            "--num_train_epochs", 5,
            "--weight_decay", 0.01,
            "--disable_tqdm", False,
        ],
        compute_target=target,
        environment=environment,
    )

    # submit script to AML
    run = exp.submit(config)
    run.set_tags(
        {
            "task": glue_task,
            "target": target_name,
            "environment": environment.name,
            "model": model_checkpoint,
        }
    )

    return run

def create_transformers_environment(workspace):
    """Register transformers gpu-base image to workspace."""
    env_name = "transformers-gpu"
    if env_name not in workspace.environments:

        # get root of git repo
        prefix = Path(__file__).parent.parent.parent.absolute()
        pip_requirements_path = prefix.joinpath("environments", "transformers-requirements.txt")
        print(f"Create Azure ML Environment {env_name} from {pip_requirements_path}")
        env = Environment.from_pip_requirements(
            name=env_name, file_path=pip_requirements_path,
        )
        env.docker.base_image = "mcr.microsoft.com/azureml/intelmpi2018.3-cuda10.0-cudnn7-ubuntu16.04"
        return env


if __name__ == "__main__":

    ws = Workspace.from_config()

    env = create_transformers_environment(ws)

    target_names = ["cpu-cluster", "gpu-cluster", "gpu-K80-2",]

    for target_name in target_names:
        run = submit_aml_run(
            workspace=ws,
            target_name=target_name,
            experiment_name="transformers-glue-finetuning-sku-comparison",
            environment=env,
            glue_task="cola",
            model_checkpoint="distilbert-base-uncased",
        )

    print(run.get_portal_url())