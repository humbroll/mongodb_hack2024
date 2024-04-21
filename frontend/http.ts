import Axios, { AxiosResponse } from "axios";
import axios from "axios";

import { Region } from "react-native-maps";
import { setupCache } from "axios-cache-interceptor";

import AppConfig from "../constants/AppConfig";
import {
  Docent,
  DocentTargetGroup,
  Poi,
  BootupResponse,
  DocentDetailsResponse,
  DocentTargetGroupDetailsResponse,
  ExploreResponse,
  LiveTourResponse,
  DocentTargetViewportSearchResponse,
  FavoritesResponse,
  AddFavoritesResponse,
  ExploreFilterCriteriaResponse,
  ChatMessage
} from "../types";
import { ErrorCode } from "../store/api/ErrorCode";
import { regionToViewport } from "./locations";
import { logCustomEvent } from "./analytics";


  interface MessageProps {
    message: ChatMessage;
  }
  
  export const sendMessage = async (props: MessageProps) =>
    new Promise<string>((resolve, reject) => {
      axios
        .post(
          `${AppConfig.baseUrl}/api/v1/chat/messages`,
          {
            text: props.message.text,
            id: props.message._id,
            user_metadata: props.message.user_metadata,
            createdAt: props.message.createdAt,
          },
          { headers }
        )
        .then((res: AxiosResponse) => {
          if (!res.data?.data?.message) {
            reject(ErrorCode.invalidApiResponse);
          }
  
          resolve(res.data.data.message);
        })
        .catch((error) => {
          reject(error);
        })
        .finally(() => {
          // logCustomEvent("send_chat_message");
        });
    });

