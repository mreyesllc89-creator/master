//+------------------------------------------------------------------+
//|                                                    Telegram.mqh   |
//|   TokioQuant - Notificaciones via WebRequest (sin DLL)            |
//|   Recuerda habilitar la URL api.telegram.org en                  |
//|   Herramientas > Opciones > Expert Advisors > WebRequest.        |
//+------------------------------------------------------------------+
#ifndef TOKIO_TELEGRAM_MQH
#define TOKIO_TELEGRAM_MQH

#include "Utilities.mqh"

class CTelegram
{
private:
   bool   m_enabled;
   string m_token;
   string m_chat;

   // Codifica una cadena para uso en URL/x-www-form-urlencoded (UTF-8).
   string UrlEncode(const string s)
   {
      uchar bytes[];
      int n = StringToCharArray(s, bytes, 0, WHOLE_ARRAY, CP_UTF8);
      string out = "";
      for(int i = 0; i < n; i++)
      {
         uchar c = bytes[i];
         if(c == 0) continue;
         if((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||
            c=='-'||c=='_'||c=='.'||c=='~')
            out += CharToString(c);
         else
            out += StringFormat("%%%02X", c);
      }
      return out;
   }

public:
   CTelegram(void) : m_enabled(false), m_token(""), m_chat("") {}

   void Init(const SConfig &cfg)
   {
      m_enabled = cfg.tg;
      m_token   = cfg.tgToken;
      m_chat    = cfg.tgChat;
   }

   // Envia un mensaje HTML. Devuelve true si la peticion salio.
   bool Send(const string message)
   {
      if(!m_enabled || m_token == "" || m_chat == "") return false;

      string url = "https://api.telegram.org/bot" + m_token + "/sendMessage";
      string payload = "chat_id=" + m_chat +
                       "&text=" + UrlEncode(message) +
                       "&parse_mode=HTML&disable_notification=false";

      char post[], result[];
      string rh;
      int len = StringLen(payload);
      StringToCharArray(payload, post, 0, len);   // sin el terminador nulo

      ResetLastError();
      int res = WebRequest("POST", url,
                           "Content-Type: application/x-www-form-urlencoded\r\n",
                           5000, post, result, rh);
      if(res == -1)
      {
         Print("Telegram WebRequest error=", GetLastError(),
               " (habilita la URL en Opciones > Expert Advisors)");
         return false;
      }
      return true;
   }
};

#endif // TOKIO_TELEGRAM_MQH
