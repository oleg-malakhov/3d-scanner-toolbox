using Common;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace PluginRotaryREST
{
   class PluginUtils
   {
      //////////////////////////////////////////////////////////////////////////
      // PluginID::rotaryID
      // PluginID::scannerID::camID
      //////////////////////////////////////////////////////////////////////////

      public const string tokenizer = "::";

      public static string[] tokenizeID(string ID)
      {
         Report.Info("PluginUtils::tokenizeID");
         return ID.Split(new string[] { tokenizer }, StringSplitOptions.None);
      }

      //////////////////////////////////////////////////////////////////////////
      //
      //////////////////////////////////////////////////////////////////////////

      public static string parsePluginID(string ID)
      {
         Report.Info("PluginUtils::parsePluginID");
         string[] tokens = tokenizeID(ID);
         if (tokens.Length < 1) return null;

         return tokens[0];
      }

      //////////////////////////////////////////////////////////////////////////
      //
      //////////////////////////////////////////////////////////////////////////

      public static string parseDeviceID(string ID)
      {
         Report.Info("PluginUtils::parseDeviceID");
         string[] tokens = tokenizeID(ID);
         if (tokens.Length < 2) return null;

         return tokens[1];
      }

      //////////////////////////////////////////////////////////////////////////
      //
      //////////////////////////////////////////////////////////////////////////
   }
}
