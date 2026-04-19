# -----------------------------------------
# Build chat memory messages
# -----------------------------------------

from langchain_core.messages import HumanMessage

def build_messages(query, memory_on, history):

    # If memory ON → include previous chats
    if memory_on:
        msgs = history.copy()
        msgs.append(HumanMessage(content=query))
        return msgs

    # If OFF → fresh chat
    return [HumanMessage(content=query)]