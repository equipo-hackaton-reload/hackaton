import { createContext } from "react";

/** True cuando el estudio está en estado `error`: las esperas dejan de decir que se actualizan solas. */
export const FalloContext = createContext(false);
