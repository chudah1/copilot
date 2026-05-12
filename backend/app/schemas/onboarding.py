from pydantic import BaseModel


class OnboardingStepStatus(BaseModel):
    done: bool
    count: int | None = None


class OnboardingStatusResponse(BaseModel):
    completed: bool
    current_step: str | None
    steps: dict[str, OnboardingStepStatus]
