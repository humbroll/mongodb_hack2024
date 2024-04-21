from typing import Any, List, Optional, Dict, Union
import logging
import datetime
import time

from colorama import Fore, Style

from app.db.firestore import firestore, crud as f_crud, schemas as f_schemas

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
    Security,
)
from pydantic import BaseModel, Field, Json, constr
import app.libs.web_response as web_res
from app.libs.place import place_utils
from app.db import crud, schemas
from app.core.security import auth_api_key
from app.db.session import get_write_db, get_read_db
from app.libs.gpt_researcher import GPTResearcher
from app.libs.gpt_researcher.scraper.scraper import Scraper
from app.libs.ai import ai_gateway

chat_router = r = APIRouter()
logger = logging.getLogger(__name__)


class NewMessageRequest(BaseModel):
    id: str
    text: str
    createdAt: str
    user_metadata: Optional[f_schemas.UserMessageMetadata] = None


@r.post("/messages")
async def new_message(
    request: NewMessageRequest,
    http_request: Request,
    db=Depends(get_read_db),
    firestore_db=Depends(firestore.get_firestore_client),
    api_key: str = Security(auth_api_key),
):
    # TODO do async as client doesn't need to wait for response
    id = request.id
    text = request.text
    created_at = request.createdAt
    user_metadata = request.user_metadata

    firebase_uid = http_request.state.user.firebase_uid

    prev_msgs = f_crud.get_messages_by_user_id(
        firestore_db, firebase_uid, limit=10, offset=0
    )

    user_message = f_crud.create_message(
        firestore_db,
        firebase_uid,
        f_schemas.MessageCreate(
            text=text,
            ai_agent=False,
            createdAt=created_at,
            user_metadata=user_metadata,
        ),
    )

    # Fetch contextual data based on the metadata in the user message
    geo_data = user_metadata.geo_data
    latitude = geo_data.latitude
    longitude = geo_data.longitude

    print(
        Fore.GREEN
        + f"Latitude: {latitude}, Longitude: {longitude}"
        + Style.RESET_ALL
    )
    # nearby search
    docent_targets = crud.search_nearby_docent_targets(
        db,
        schemas.SearchNearby(
            latitude=latitude,
            longitude=longitude,
            radius=1000,
            active_only=True,
        ),
        has_narrative_list=True,
        limit=5,
    )
    docent_target = docent_targets[0] if docent_targets else None

    if not docent_target:
        message = "Couldn't find any attractions nearby."
        docentpro_message = f_crud.create_message(
            firestore_db,
            firebase_uid,
            f_schemas.MessageCreate(
                text=message,
                markdown_text=message,
                ai_agent=True,
                createdAt=datetime.datetime.now().isoformat(),
            ),
        )
    else:
        print(
            Fore.GREEN
            + f"Docent Target: {docent_target.place.name}"
            + Style.RESET_ALL
        )
        # res_message = "com.docentpro.mobile://docent-target-details/1343/play"
        res_message = ai_gateway.chat(
            text,
            place=docent_target.place,
            # prev_msgs=prev_msgs,
            extensive=True,
            language="English",
            ai_platform="upstage",
        )

        target_data = schemas.DocentTargetForCardApi.from_orm(docent_target)
        photo_url = target_data.photos[0].url

        docentpro_message = f_crud.create_message(
            firestore_db,
            firebase_uid,
            f_schemas.MessageCreate(
                text=res_message,
                markdown_text=res_message,
                ai_agent=True,
                createdAt=datetime.datetime.now().isoformat(),
                docentpro_metadata=f_schemas.DocentProMessageMetadata(
                    medias=[
                        f_schemas.DocentProMessageMedia(
                            title=docent_target.place.name,
                            type=f_schemas.DocentProMessageMediaTypes.IMAGE,
                            url=photo_url,
                        )
                    ]
                ),
            ),
        )

    return web_res.success_response(
        {
            "user_message": user_message,
            "docentpro_message": docentpro_message,
        }
    )
