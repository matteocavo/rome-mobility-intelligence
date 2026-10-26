from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/model/info")
def model_info(request: Request):
    model = request.app.state.model
    if model is None:
        raise HTTPException(503, "No validated model loaded")
    return model.info()
