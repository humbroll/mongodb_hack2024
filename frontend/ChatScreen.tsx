import React, { memo, useEffect, useRef, useState, useMemo, useCallback, useLayoutEffect } from "react";
import { GiftedChat } from "react-native-gifted-chat";
import {
  StyleSheet,
  View
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import {
  collection,
  addDoc,
  orderBy,
  query,
  where,
  onSnapshot,
} from 'firebase/firestore';

import { sendMessage } from "../../utils/http";
import { ChatMessage } from "../../types";
import {
  fetchMyLocation,
  requestForegroundLocationPermissions,
} from "../../utils/locations";
import { useDocentConfig, useDocentInfoV2, useTheme, useTranslations } from "../../store";
import { HomeStackProps, HomeStackRoutes } from "../../navigation";
import { ThemeColorSet } from "../../constants/theme";
import { events } from "../../utils/analytics";
import { useCurrentUser } from "../../store/hooks";
import { PlayBar } from "../../components";
import { db } from "../../store/api/firebase";

export const ChatScreen = memo(
  (props: HomeStackProps<HomeStackRoutes.SETTINGS>): JSX.Element => {
    const {
      theme: { colorSet },
    } = useTheme();
    const { top } = useSafeAreaInsets();
    const [isLoading, setIsLoading] = useState(false);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const { localized } = useTranslations();
    const styles = dynamicStyles(colorSet, top);
    const currentUser = useCurrentUser();


    useEffect(() => {
    }, [])

    useLayoutEffect(() => {
      const messagesRef = collection(db, 'chatrooms', 'chatroom_'+currentUser.uid, 'messages');
      const q = query(messagesRef, orderBy('createdAt', 'desc'));

      const unsubscribe = onSnapshot(q, querySnapshot => {
        console.log('querySnapshot unsusbscribe');
        console.log(querySnapshot.docs)
        setMessages(
          querySnapshot.docs.map(doc => ({
            _id: doc.data()._id,
            createdAt: doc.data().createdAt.toDate(),
            text: doc.data().markdown_text || doc.data().text,
            user: {
              _id: doc.data().ai_agent ? 0 : currentUser?.uid,
            },
            image: doc.data().docentpro_metadata?.medias?.[0]?.url,
          }))
        );
      });
      return unsubscribe;
    }, [])
  
    const onSend = async (messages = []) => {
      // try {
      await requestForegroundLocationPermissions(localized);
      const location = await fetchMyLocation(localized);
      // } catch (error) {
      //   // We don't need error handling here, as getExplore works without location
      //   console.log(error);
      // }

      const updatedMessages = messages.map(message => ({
      ...message,
      user_metadata: {
        "geo_data": {
        "latitude": location.coords?.latitude ?? 0,
        "longitude": location.coords?.longitude ?? 0,
        },
      }
      }));

      setMessages(previousMessages =>
      GiftedChat.append(previousMessages, updatedMessages),
      );

      setIsLoading(true);

      try {
      await sendMessage({
        message: updatedMessages[0],
      });
      } catch (error) {
      console.log("sendMessage error: ", error);
      } finally {
      setIsLoading(false);
      }
    };

    return (
      <View style={styles.container}>
        <GiftedChat
          messages={messages}
          onSend={messages => onSend(messages)}
          user={{
            _id: currentUser?.uid,
          }}
          messagesContainerStyle={{
            backgroundColor: colorSet.white
          }}
        />
        <PlayBar />
      </View>

    );
  }
);


const dynamicStyles = (colorSet: ThemeColorSet, top: number) =>
  StyleSheet.create({
    container: {
      position: "relative",
      flex: 1,
      width: "100%",
      height: "100%",
      paddingTop: top,
      backgroundColor: colorSet.primaryBackground,
    },
    bottomSheetHandle: {
      borderBottomWidth: 0,
      backgroundColor: colorSet.primaryBackground,
    },
    bottomSheetContainer: {
      backgroundColor: colorSet.primaryBackground,
    },
    container: {
      width: "100%",
      flex: 1,
    },
    chatContainer: {
      flex: 1,
    },
  });

export default ChatScreen;