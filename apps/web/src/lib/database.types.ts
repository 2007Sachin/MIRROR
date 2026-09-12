export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      assessment_adjudications: {
        Row: {
          affected_dimension: string
          confidence: number
          created_at: string
          final_decision: Json
          id: string
          model: string
          prompt_version: string
          session_id: string
          specialist_inputs: Json
        }
        Insert: {
          affected_dimension: string
          confidence: number
          created_at?: string
          final_decision: Json
          id?: string
          model: string
          prompt_version: string
          session_id: string
          specialist_inputs: Json
        }
        Update: {
          affected_dimension?: string
          confidence?: number
          created_at?: string
          final_decision?: Json
          id?: string
          model?: string
          prompt_version?: string
          session_id?: string
          specialist_inputs?: Json
        }
        Relationships: [
          {
            foreignKeyName: "assessment_adjudications_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      assessment_disputes: {
        Row: {
          comment: string | null
          created_at: string
          id: string
          reason: string
          session_id: string
          target_id: string
          target_type: string
          user_id: string
        }
        Insert: {
          comment?: string | null
          created_at?: string
          id?: string
          reason: string
          session_id: string
          target_id: string
          target_type: string
          user_id: string
        }
        Update: {
          comment?: string | null
          created_at?: string
          id?: string
          reason?: string
          session_id?: string
          target_id?: string
          target_type?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "assessment_disputes_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "assessment_disputes_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      calibration_runs: {
        Row: {
          auc: number | null
          band_distribution: Json
          created_at: string
          drift_flag: boolean
          golden_set_version: string
          id: string
          model_version: string
          rubric_version: string
        }
        Insert: {
          auc?: number | null
          band_distribution: Json
          created_at?: string
          drift_flag?: boolean
          golden_set_version: string
          id?: string
          model_version: string
          rubric_version: string
        }
        Update: {
          auc?: number | null
          band_distribution?: Json
          created_at?: string
          drift_flag?: boolean
          golden_set_version?: string
          id?: string
          model_version?: string
          rubric_version?: string
        }
        Relationships: []
      }
      claim_entities: {
        Row: {
          canonical_key: string | null
          canonical_name: string
          created_at: string
          entity_type: Database["public"]["Enums"]["claim_entity_type"]
          id: string
          metadata: Json
          user_id: string
        }
        Insert: {
          canonical_key?: string | null
          canonical_name: string
          created_at?: string
          entity_type: Database["public"]["Enums"]["claim_entity_type"]
          id?: string
          metadata?: Json
          user_id: string
        }
        Update: {
          canonical_key?: string | null
          canonical_name?: string
          created_at?: string
          entity_type?: Database["public"]["Enums"]["claim_entity_type"]
          id?: string
          metadata?: Json
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "claim_entities_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      claim_evidence: {
        Row: {
          agent_model: string | null
          claim_id: string
          created_at: string
          document_id: string | null
          evidence_direction: Database["public"]["Enums"]["evidence_direction"]
          evidence_execution_id: string | null
          evidence_key: string | null
          evidence_strength: string | null
          evidence_type: Database["public"]["Enums"]["claim_evidence_type"]
          id: string
          prompt_version: string | null
          quote_text: string | null
          reason_code: string | null
          source_id: string | null
          source_type: string | null
          strength: number
          turn_id: string | null
          user_id: string
          validated: boolean
        }
        Insert: {
          agent_model?: string | null
          claim_id: string
          created_at?: string
          document_id?: string | null
          evidence_direction: Database["public"]["Enums"]["evidence_direction"]
          evidence_execution_id?: string | null
          evidence_key?: string | null
          evidence_strength?: string | null
          evidence_type: Database["public"]["Enums"]["claim_evidence_type"]
          id?: string
          prompt_version?: string | null
          quote_text?: string | null
          reason_code?: string | null
          source_id?: string | null
          source_type?: string | null
          strength: number
          turn_id?: string | null
          user_id: string
          validated?: boolean
        }
        Update: {
          agent_model?: string | null
          claim_id?: string
          created_at?: string
          document_id?: string | null
          evidence_direction?: Database["public"]["Enums"]["evidence_direction"]
          evidence_execution_id?: string | null
          evidence_key?: string | null
          evidence_strength?: string | null
          evidence_type?: Database["public"]["Enums"]["claim_evidence_type"]
          id?: string
          prompt_version?: string | null
          quote_text?: string | null
          reason_code?: string | null
          source_id?: string | null
          source_type?: string | null
          strength?: number
          turn_id?: string | null
          user_id?: string
          validated?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "claim_evidence_claim_id_fkey"
            columns: ["claim_id"]
            isOneToOne: false
            referencedRelation: "claims"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claim_evidence_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claim_evidence_turn_id_fkey"
            columns: ["turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claim_evidence_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      claim_relations: {
        Row: {
          confidence: number
          created_at: string
          id: string
          relation_type: Database["public"]["Enums"]["claim_relation_type"]
          source: Database["public"]["Enums"]["claim_relation_source"]
          source_entity_id: string
          source_entity_type: Database["public"]["Enums"]["claim_graph_node_type"]
          target_entity_id: string
          target_entity_type: Database["public"]["Enums"]["claim_graph_node_type"]
          user_id: string
        }
        Insert: {
          confidence: number
          created_at?: string
          id?: string
          relation_type: Database["public"]["Enums"]["claim_relation_type"]
          source: Database["public"]["Enums"]["claim_relation_source"]
          source_entity_id: string
          source_entity_type: Database["public"]["Enums"]["claim_graph_node_type"]
          target_entity_id: string
          target_entity_type: Database["public"]["Enums"]["claim_graph_node_type"]
          user_id: string
        }
        Update: {
          confidence?: number
          created_at?: string
          id?: string
          relation_type?: Database["public"]["Enums"]["claim_relation_type"]
          source?: Database["public"]["Enums"]["claim_relation_source"]
          source_entity_id?: string
          source_entity_type?: Database["public"]["Enums"]["claim_graph_node_type"]
          target_entity_id?: string
          target_entity_type?: Database["public"]["Enums"]["claim_graph_node_type"]
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "claim_relations_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      claim_resolutions: {
        Row: {
          claim_id: string
          confidence: number
          created_at: string
          evidence_ids: string[]
          id: string
          new_status: Database["public"]["Enums"]["claim_status"]
          previous_status: Database["public"]["Enums"]["claim_status"]
          resolution_reason: string
          trigger_type: Database["public"]["Enums"]["claim_resolution_trigger"]
          user_id: string
        }
        Insert: {
          claim_id: string
          confidence: number
          created_at?: string
          evidence_ids?: string[]
          id?: string
          new_status: Database["public"]["Enums"]["claim_status"]
          previous_status: Database["public"]["Enums"]["claim_status"]
          resolution_reason: string
          trigger_type: Database["public"]["Enums"]["claim_resolution_trigger"]
          user_id: string
        }
        Update: {
          claim_id?: string
          confidence?: number
          created_at?: string
          evidence_ids?: string[]
          id?: string
          new_status?: Database["public"]["Enums"]["claim_status"]
          previous_status?: Database["public"]["Enums"]["claim_status"]
          resolution_reason?: string
          trigger_type?: Database["public"]["Enums"]["claim_resolution_trigger"]
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "claim_resolutions_claim_id_fkey"
            columns: ["claim_id"]
            isOneToOne: false
            referencedRelation: "claims"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claim_resolutions_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      claim_versions: {
        Row: {
          changed_by: Database["public"]["Enums"]["claim_changed_by"]
          claim_id: string
          created_at: string
          id: string
          new_state: Json
          previous_state: Json | null
          reason: string
          user_id: string
          version: number
        }
        Insert: {
          changed_by: Database["public"]["Enums"]["claim_changed_by"]
          claim_id: string
          created_at?: string
          id?: string
          new_state: Json
          previous_state?: Json | null
          reason: string
          user_id: string
          version: number
        }
        Update: {
          changed_by?: Database["public"]["Enums"]["claim_changed_by"]
          claim_id?: string
          created_at?: string
          id?: string
          new_state?: Json
          previous_state?: Json | null
          reason?: string
          user_id?: string
          version?: number
        }
        Relationships: [
          {
            foreignKeyName: "claim_versions_claim_id_fkey"
            columns: ["claim_id"]
            isOneToOne: false
            referencedRelation: "claims"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claim_versions_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      claims: {
        Row: {
          claim_text: string
          claim_type: Database["public"]["Enums"]["claim_type"]
          confidence: number
          contradicted_by_turn_id: string | null
          created_at: string
          id: string
          metric_unit: string | null
          metric_value: number | null
          outcome: string | null
          ownership_language: string | null
          project_name: string | null
          resume_analysis_id: string | null
          session_id: string | null
          skill: string | null
          source: Database["public"]["Enums"]["claim_source"]
          source_document_id: string | null
          source_ref: string | null
          source_reference: string | null
          status: Database["public"]["Enums"]["claim_status"]
          synthetic: boolean
          tool: string | null
          updated_at: string
          user_id: string
          verification_priority: Database["public"]["Enums"]["verification_priority"]
        }
        Insert: {
          claim_text: string
          claim_type: Database["public"]["Enums"]["claim_type"]
          confidence: number
          contradicted_by_turn_id?: string | null
          created_at?: string
          id?: string
          metric_unit?: string | null
          metric_value?: number | null
          outcome?: string | null
          ownership_language?: string | null
          project_name?: string | null
          resume_analysis_id?: string | null
          session_id?: string | null
          skill?: string | null
          source: Database["public"]["Enums"]["claim_source"]
          source_document_id?: string | null
          source_ref?: string | null
          source_reference?: string | null
          status?: Database["public"]["Enums"]["claim_status"]
          synthetic?: boolean
          tool?: string | null
          updated_at?: string
          user_id: string
          verification_priority?: Database["public"]["Enums"]["verification_priority"]
        }
        Update: {
          claim_text?: string
          claim_type?: Database["public"]["Enums"]["claim_type"]
          confidence?: number
          contradicted_by_turn_id?: string | null
          created_at?: string
          id?: string
          metric_unit?: string | null
          metric_value?: number | null
          outcome?: string | null
          ownership_language?: string | null
          project_name?: string | null
          resume_analysis_id?: string | null
          session_id?: string | null
          skill?: string | null
          source?: Database["public"]["Enums"]["claim_source"]
          source_document_id?: string | null
          source_ref?: string | null
          source_reference?: string | null
          status?: Database["public"]["Enums"]["claim_status"]
          synthetic?: boolean
          tool?: string | null
          updated_at?: string
          user_id?: string
          verification_priority?: Database["public"]["Enums"]["verification_priority"]
        }
        Relationships: [
          {
            foreignKeyName: "claims_contradicted_by_turn_id_fkey"
            columns: ["contradicted_by_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claims_resume_analysis_id_fkey"
            columns: ["resume_analysis_id"]
            isOneToOne: false
            referencedRelation: "resume_analyses"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claims_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claims_source_document_id_fkey"
            columns: ["source_document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "claims_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      colleges: {
        Row: {
          created_at: string
          id: string
          name: string
        }
        Insert: {
          created_at?: string
          id?: string
          name: string
        }
        Update: {
          created_at?: string
          id?: string
          name?: string
        }
        Relationships: []
      }
      detailed_food_logs: {
        Row: {
          calories: number | null
          carbs_g: number | null
          confidence_score: number | null
          created_at: string | null
          fats_g: number | null
          fiber_g: number | null
          food_name: string | null
          health_warning: string | null
          id: number
          input_source: string | null
          logged_at: string
          meal_type: string | null
          original_text: string | null
          protein_g: number | null
          sodium_mg: number | null
          sugar_g: number | null
          user_id: string | null
        }
        Insert: {
          calories?: number | null
          carbs_g?: number | null
          confidence_score?: number | null
          created_at?: string | null
          fats_g?: number | null
          fiber_g?: number | null
          food_name?: string | null
          health_warning?: string | null
          id?: number
          input_source?: string | null
          logged_at?: string
          meal_type?: string | null
          original_text?: string | null
          protein_g?: number | null
          sodium_mg?: number | null
          sugar_g?: number | null
          user_id?: string | null
        }
        Update: {
          calories?: number | null
          carbs_g?: number | null
          confidence_score?: number | null
          created_at?: string | null
          fats_g?: number | null
          fiber_g?: number | null
          food_name?: string | null
          health_warning?: string | null
          id?: number
          input_source?: string | null
          logged_at?: string
          meal_type?: string | null
          original_text?: string | null
          protein_g?: number | null
          sodium_mg?: number | null
          sugar_g?: number | null
          user_id?: string | null
        }
        Relationships: []
      }
      documents: {
        Row: {
          archived_at: string | null
          context_note: string | null
          created_at: string
          document_type: Database["public"]["Enums"]["document_type"]
          evidence_category: Database["public"]["Enums"]["evidence_category"]
          error_message: string | null
          id: string
          mime_type: string | null
          original_filename: string | null
          processed_at: string | null
          raw_text: string | null
          status: Database["public"]["Enums"]["document_status"]
          storage_path: string | null
          supersedes_document_id: string | null
          title: string
          updated_at: string
          user_id: string
          version_number: number
        }
        Insert: {
          archived_at?: string | null
          context_note?: string | null
          created_at?: string
          document_type: Database["public"]["Enums"]["document_type"]
          evidence_category: Database["public"]["Enums"]["evidence_category"]
          error_message?: string | null
          id?: string
          mime_type?: string | null
          original_filename?: string | null
          processed_at?: string | null
          raw_text?: string | null
          status: Database["public"]["Enums"]["document_status"]
          storage_path?: string | null
          supersedes_document_id?: string | null
          title: string
          updated_at?: string
          user_id: string
          version_number?: number
        }
        Update: {
          archived_at?: string | null
          context_note?: string | null
          created_at?: string
          document_type?: Database["public"]["Enums"]["document_type"]
          evidence_category?: Database["public"]["Enums"]["evidence_category"]
          error_message?: string | null
          id?: string
          mime_type?: string | null
          original_filename?: string | null
          processed_at?: string | null
          raw_text?: string | null
          status?: Database["public"]["Enums"]["document_status"]
          storage_path?: string | null
          supersedes_document_id?: string | null
          title?: string
          updated_at?: string
          user_id?: string
          version_number?: number
        }
        Relationships: [
          {
            foreignKeyName: "documents_supersedes_document_id_fkey"
            columns: ["supersedes_document_id"]
            isOneToOne: true
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "documents_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      flags: {
        Row: {
          claim_id: string | null
          confidence: number
          consumed: boolean
          consumed_at: string | null
          consumed_at_turn: number | null
          created_at: string
          dedupe_key: string | null
          detected_at_turn: number
          dispute_reason: string | null
          disputed: boolean
          distinction: string
          flag_type: Database["public"]["Enums"]["flag_type"]
          id: string
          interviewer_turn_id: string | null
          reason: string
          related_turn_ids: string[]
          resolved_at: string | null
          safe_to_surface: boolean
          session_id: string
          severity: string
          shadow_mode: boolean
          skeptic_execution_id: string | null
          source_turn_id: string | null
          suggested_probe: string
        }
        Insert: {
          claim_id?: string | null
          confidence: number
          consumed?: boolean
          consumed_at?: string | null
          consumed_at_turn?: number | null
          created_at?: string
          dedupe_key?: string | null
          detected_at_turn: number
          dispute_reason?: string | null
          disputed?: boolean
          distinction: string
          flag_type: Database["public"]["Enums"]["flag_type"]
          id?: string
          interviewer_turn_id?: string | null
          reason: string
          related_turn_ids?: string[]
          resolved_at?: string | null
          safe_to_surface?: boolean
          session_id: string
          severity: string
          shadow_mode?: boolean
          skeptic_execution_id?: string | null
          source_turn_id?: string | null
          suggested_probe: string
        }
        Update: {
          claim_id?: string | null
          confidence?: number
          consumed?: boolean
          consumed_at?: string | null
          consumed_at_turn?: number | null
          created_at?: string
          dedupe_key?: string | null
          detected_at_turn?: number
          dispute_reason?: string | null
          disputed?: boolean
          distinction?: string
          flag_type?: Database["public"]["Enums"]["flag_type"]
          id?: string
          interviewer_turn_id?: string | null
          reason?: string
          related_turn_ids?: string[]
          resolved_at?: string | null
          safe_to_surface?: boolean
          session_id?: string
          severity?: string
          shadow_mode?: boolean
          skeptic_execution_id?: string | null
          source_turn_id?: string | null
          suggested_probe?: string
        }
        Relationships: [
          {
            foreignKeyName: "flags_claim_id_fkey"
            columns: ["claim_id"]
            isOneToOne: false
            referencedRelation: "claims"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "flags_interviewer_turn_id_fkey"
            columns: ["interviewer_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "flags_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "flags_source_turn_id_fkey"
            columns: ["source_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
        ]
      }
      golden_cases: {
        Row: {
          case_type: string
          created_at: string
          expected_claim_states: Json
          expected_flags: Json
          expected_score_band: Json
          id: string
          source: string
          transcript: Json
          version: string
        }
        Insert: {
          case_type: string
          created_at?: string
          expected_claim_states: Json
          expected_flags: Json
          expected_score_band: Json
          id?: string
          source: string
          transcript: Json
          version: string
        }
        Update: {
          case_type?: string
          created_at?: string
          expected_claim_states?: Json
          expected_flags?: Json
          expected_score_band?: Json
          id?: string
          source?: string
          transcript?: Json
          version?: string
        }
        Relationships: []
      }
      interview_plans: {
        Row: {
          active: boolean
          completed_at: string | null
          created_at: string
          error_type: string | null
          execution_id: string | null
          id: string
          plan_json: Json | null
          planner_model: string
          planning_version: string
          prompt_version: string
          session_id: string
          status: Database["public"]["Enums"]["interview_plan_status"]
          user_id: string
          version: number
        }
        Insert: {
          active?: boolean
          completed_at?: string | null
          created_at?: string
          error_type?: string | null
          execution_id?: string | null
          id?: string
          plan_json?: Json | null
          planner_model: string
          planning_version: string
          prompt_version: string
          session_id: string
          status?: Database["public"]["Enums"]["interview_plan_status"]
          user_id: string
          version: number
        }
        Update: {
          active?: boolean
          completed_at?: string | null
          created_at?: string
          error_type?: string | null
          execution_id?: string | null
          id?: string
          plan_json?: Json | null
          planner_model?: string
          planning_version?: string
          prompt_version?: string
          session_id?: string
          status?: Database["public"]["Enums"]["interview_plan_status"]
          user_id?: string
          version?: number
        }
        Relationships: [
          {
            foreignKeyName: "interview_plans_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "interview_plans_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      jobs: {
        Row: {
          attempts: number
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          error: string | null
          id: string
          job_type: string
          locked_at: string | null
          locked_by: string | null
          payload: Json
          run_after: string
          status: Database["public"]["Enums"]["job_status"]
          updated_at: string
        }
        Insert: {
          attempts?: number
          completed_at?: string | null
          created_at?: string
          dedupe_key?: string | null
          error?: string | null
          id?: string
          job_type: string
          locked_at?: string | null
          locked_by?: string | null
          payload: Json
          run_after?: string
          status?: Database["public"]["Enums"]["job_status"]
          updated_at?: string
        }
        Update: {
          attempts?: number
          completed_at?: string | null
          created_at?: string
          dedupe_key?: string | null
          error?: string | null
          id?: string
          job_type?: string
          locked_at?: string | null
          locked_by?: string | null
          payload?: Json
          run_after?: string
          status?: Database["public"]["Enums"]["job_status"]
          updated_at?: string
        }
        Relationships: []
      }
      model_events: {
        Row: {
          created_at: string
          id: string
          latency_ms: number
          model_name: string | null
          model_provider: string | null
          model_version: string | null
          operation: string
          parsing_failed: boolean
          prompt_version: string | null
          retry_count: number
          session_id: string | null
          token_usage: Json | null
          turn_id: string | null
        }
        Insert: {
          created_at?: string
          id?: string
          latency_ms: number
          model_name?: string | null
          model_provider?: string | null
          model_version?: string | null
          operation: string
          parsing_failed?: boolean
          prompt_version?: string | null
          retry_count?: number
          session_id?: string | null
          token_usage?: Json | null
          turn_id?: string | null
        }
        Update: {
          created_at?: string
          id?: string
          latency_ms?: number
          model_name?: string | null
          model_provider?: string | null
          model_version?: string | null
          operation?: string
          parsing_failed?: boolean
          prompt_version?: string | null
          retry_count?: number
          session_id?: string | null
          token_usage?: Json | null
          turn_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "model_events_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "model_events_turn_id_fkey"
            columns: ["turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
        ]
      }
      nutrition_goals: {
        Row: {
          created_at: string
          goal_period: string
          goal_type: string
          id: number
          target_value: number
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          goal_period?: string
          goal_type: string
          id?: number
          target_value: number
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          goal_period?: string
          goal_type?: string
          id?: number
          target_value?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      outcomes: {
        Row: {
          company_id: string | null
          created_at: string
          id: string
          linked_session_id: string | null
          result: string
          source: string
          user_id: string
          verified: boolean
        }
        Insert: {
          company_id?: string | null
          created_at?: string
          id?: string
          linked_session_id?: string | null
          result: string
          source: string
          user_id: string
          verified?: boolean
        }
        Update: {
          company_id?: string | null
          created_at?: string
          id?: string
          linked_session_id?: string | null
          result?: string
          source?: string
          user_id?: string
          verified?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "outcomes_linked_session_id_fkey"
            columns: ["linked_session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "outcomes_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          career_intent: Database["public"]["Enums"]["career_intent"] | null
          career_stage: Database["public"]["Enums"]["career_stage"] | null
          college_id: string | null
          created_at: string
          current_role_profile_id: string | null
          email: string | null
          full_name: string | null
          id: string
          interview_timeline:
            | Database["public"]["Enums"]["interview_timeline"]
            | null
          inquiry_depth: Database["public"]["Enums"]["inquiry_depth"][]
          onboarding_completed: boolean
          onboarding_resume_document_id: string | null
          onboarding_role_brief_document_id: string | null
          onboarding_role_brief_skipped: boolean
          onboarding_role_profile_id: string | null
          onboarding_session_id: string | null
          onboarding_step: number
          preferred_language:
            | Database["public"]["Enums"]["preferred_language"]
            | null
          role: string
          target_company: string | null
          target_role: string | null
          updated_at: string
        }
        Insert: {
          career_intent?: Database["public"]["Enums"]["career_intent"] | null
          career_stage?: Database["public"]["Enums"]["career_stage"] | null
          college_id?: string | null
          created_at?: string
          current_role_profile_id?: string | null
          email?: string | null
          full_name?: string | null
          id: string
          interview_timeline?:
            | Database["public"]["Enums"]["interview_timeline"]
            | null
          inquiry_depth?: Database["public"]["Enums"]["inquiry_depth"][]
          onboarding_completed?: boolean
          onboarding_resume_document_id?: string | null
          onboarding_role_brief_document_id?: string | null
          onboarding_role_brief_skipped?: boolean
          onboarding_role_profile_id?: string | null
          onboarding_session_id?: string | null
          onboarding_step?: number
          preferred_language?:
            | Database["public"]["Enums"]["preferred_language"]
            | null
          role?: string
          target_company?: string | null
          target_role?: string | null
          updated_at?: string
        }
        Update: {
          career_intent?: Database["public"]["Enums"]["career_intent"] | null
          career_stage?: Database["public"]["Enums"]["career_stage"] | null
          college_id?: string | null
          created_at?: string
          current_role_profile_id?: string | null
          email?: string | null
          full_name?: string | null
          id?: string
          interview_timeline?:
            | Database["public"]["Enums"]["interview_timeline"]
            | null
          inquiry_depth?: Database["public"]["Enums"]["inquiry_depth"][]
          onboarding_completed?: boolean
          onboarding_resume_document_id?: string | null
          onboarding_role_brief_document_id?: string | null
          onboarding_role_brief_skipped?: boolean
          onboarding_role_profile_id?: string | null
          onboarding_session_id?: string | null
          onboarding_step?: number
          preferred_language?:
            | Database["public"]["Enums"]["preferred_language"]
            | null
          role?: string
          target_company?: string | null
          target_role?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "profiles_onboarding_resume_document_id_fkey"
            columns: ["onboarding_resume_document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "profiles_onboarding_role_brief_document_id_fkey"
            columns: ["onboarding_role_brief_document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "profiles_onboarding_role_profile_id_fkey"
            columns: ["onboarding_role_profile_id"]
            isOneToOne: false
            referencedRelation: "role_profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "profiles_onboarding_session_id_fkey"
            columns: ["onboarding_session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "profiles_current_role_profile_id_fkey"
            columns: ["current_role_profile_id"]
            isOneToOne: false
            referencedRelation: "role_profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "users_college_id_fkey"
            columns: ["college_id"]
            isOneToOne: false
            referencedRelation: "colleges"
            referencedColumns: ["id"]
          },
        ]
      }
      question_bank: {
        Row: {
          canonical_text: string
          company_id: string | null
          created_at: string
          evidence_tier: string
          id: string
          report_count: number
          role_id: string | null
          round_type: Database["public"]["Enums"]["round_type"]
          skill_id: string | null
        }
        Insert: {
          canonical_text: string
          company_id?: string | null
          created_at?: string
          evidence_tier: string
          id?: string
          report_count?: number
          role_id?: string | null
          round_type: Database["public"]["Enums"]["round_type"]
          skill_id?: string | null
        }
        Update: {
          canonical_text?: string
          company_id?: string | null
          created_at?: string
          evidence_tier?: string
          id?: string
          report_count?: number
          role_id?: string | null
          round_type?: Database["public"]["Enums"]["round_type"]
          skill_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "question_bank_role_id_fkey"
            columns: ["role_id"]
            isOneToOne: false
            referencedRelation: "roles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "question_bank_skill_id_fkey"
            columns: ["skill_id"]
            isOneToOne: false
            referencedRelation: "skills"
            referencedColumns: ["id"]
          },
        ]
      }
      question_reports: {
        Row: {
          consent_given: boolean
          created_at: string
          id: string
          pii_stripped: boolean
          raw_text: string
          source: string
        }
        Insert: {
          consent_given?: boolean
          created_at?: string
          id?: string
          pii_stripped?: boolean
          raw_text: string
          source: string
        }
        Update: {
          consent_given?: boolean
          created_at?: string
          id?: string
          pii_stripped?: boolean
          raw_text?: string
          source?: string
        }
        Relationships: []
      }
      resume_analyses: {
        Row: {
          analysis_version: string
          completed_at: string | null
          created_at: string
          document_id: string
          error_type: string | null
          execution_id: string | null
          id: string
          model: string
          output: Json | null
          prompt_version: string
          status: Database["public"]["Enums"]["resume_analysis_status"]
          user_id: string
          version: number
        }
        Insert: {
          analysis_version: string
          completed_at?: string | null
          created_at?: string
          document_id: string
          error_type?: string | null
          execution_id?: string | null
          id?: string
          model: string
          output?: Json | null
          prompt_version: string
          status?: Database["public"]["Enums"]["resume_analysis_status"]
          user_id: string
          version: number
        }
        Update: {
          analysis_version?: string
          completed_at?: string | null
          created_at?: string
          document_id?: string
          error_type?: string | null
          execution_id?: string | null
          id?: string
          model?: string
          output?: Json | null
          prompt_version?: string
          status?: Database["public"]["Enums"]["resume_analysis_status"]
          user_id?: string
          version?: number
        }
        Relationships: [
          {
            foreignKeyName: "resume_analyses_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "resume_analyses_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      resume_claim_corrections: {
        Row: {
          claim_id: string
          corrected_claim_text: string | null
          created_at: string
          id: string
          resume_analysis_id: string
          review_status: Database["public"]["Enums"]["claim_review_status"]
          user_id: string
          version: number
        }
        Insert: {
          claim_id: string
          corrected_claim_text?: string | null
          created_at?: string
          id?: string
          resume_analysis_id: string
          review_status: Database["public"]["Enums"]["claim_review_status"]
          user_id: string
          version: number
        }
        Update: {
          claim_id?: string
          corrected_claim_text?: string | null
          created_at?: string
          id?: string
          resume_analysis_id?: string
          review_status?: Database["public"]["Enums"]["claim_review_status"]
          user_id?: string
          version?: number
        }
        Relationships: [
          {
            foreignKeyName: "resume_claim_corrections_claim_id_fkey"
            columns: ["claim_id"]
            isOneToOne: false
            referencedRelation: "claims"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "resume_claim_corrections_resume_analysis_id_fkey"
            columns: ["resume_analysis_id"]
            isOneToOne: false
            referencedRelation: "resume_analyses"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "resume_claim_corrections_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      role_analysis_versions: {
        Row: {
          analysis_version: string
          completed_at: string | null
          created_at: string
          error_type: string | null
          execution_id: string | null
          id: string
          model: string
          output: Json | null
          prompt_version: string
          role_profile_id: string
          source_document_id: string | null
          source_type: Database["public"]["Enums"]["role_source_type"]
          status: Database["public"]["Enums"]["role_analysis_status"]
          user_id: string
          version: number
        }
        Insert: {
          analysis_version: string
          completed_at?: string | null
          created_at?: string
          error_type?: string | null
          execution_id?: string | null
          id?: string
          model: string
          output?: Json | null
          prompt_version: string
          role_profile_id: string
          source_document_id?: string | null
          source_type: Database["public"]["Enums"]["role_source_type"]
          status?: Database["public"]["Enums"]["role_analysis_status"]
          user_id: string
          version: number
        }
        Update: {
          analysis_version?: string
          completed_at?: string | null
          created_at?: string
          error_type?: string | null
          execution_id?: string | null
          id?: string
          model?: string
          output?: Json | null
          prompt_version?: string
          role_profile_id?: string
          source_document_id?: string | null
          source_type?: Database["public"]["Enums"]["role_source_type"]
          status?: Database["public"]["Enums"]["role_analysis_status"]
          user_id?: string
          version?: number
        }
        Relationships: [
          {
            foreignKeyName: "role_analysis_versions_role_profile_id_fkey"
            columns: ["role_profile_id"]
            isOneToOne: false
            referencedRelation: "role_profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "role_analysis_versions_source_document_id_fkey"
            columns: ["source_document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "role_analysis_versions_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      role_competencies: {
        Row: {
          analysis_version_id: string
          category: Database["public"]["Enums"]["competency_category"]
          confidence: number
          created_at: string
          expected_level: Database["public"]["Enums"]["expected_competency_level"]
          id: string
          importance_weight: number
          name: string
          role_profile_id: string
          source_reference: string
          source_type: Database["public"]["Enums"]["competency_source_type"]
          user_id: string
        }
        Insert: {
          analysis_version_id: string
          category: Database["public"]["Enums"]["competency_category"]
          confidence: number
          created_at?: string
          expected_level: Database["public"]["Enums"]["expected_competency_level"]
          id?: string
          importance_weight: number
          name: string
          role_profile_id: string
          source_reference: string
          source_type: Database["public"]["Enums"]["competency_source_type"]
          user_id: string
        }
        Update: {
          analysis_version_id?: string
          category?: Database["public"]["Enums"]["competency_category"]
          confidence?: number
          created_at?: string
          expected_level?: Database["public"]["Enums"]["expected_competency_level"]
          id?: string
          importance_weight?: number
          name?: string
          role_profile_id?: string
          source_reference?: string
          source_type?: Database["public"]["Enums"]["competency_source_type"]
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "role_competencies_analysis_version_id_fkey"
            columns: ["analysis_version_id"]
            isOneToOne: false
            referencedRelation: "role_analysis_versions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "role_competencies_role_profile_id_fkey"
            columns: ["role_profile_id"]
            isOneToOne: false
            referencedRelation: "role_profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "role_competencies_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      role_profiles: {
        Row: {
          canonical_role: string | null
          created_at: string
          current_analysis_version_id: string | null
          id: string
          seniority: Database["public"]["Enums"]["role_seniority"] | null
          source_document_id: string | null
          source_type: Database["public"]["Enums"]["role_source_type"]
          target_role: string
          updated_at: string
          user_id: string
        }
        Insert: {
          canonical_role?: string | null
          created_at?: string
          current_analysis_version_id?: string | null
          id?: string
          seniority?: Database["public"]["Enums"]["role_seniority"] | null
          source_document_id?: string | null
          source_type: Database["public"]["Enums"]["role_source_type"]
          target_role: string
          updated_at?: string
          user_id: string
        }
        Update: {
          canonical_role?: string | null
          created_at?: string
          current_analysis_version_id?: string | null
          id?: string
          seniority?: Database["public"]["Enums"]["role_seniority"] | null
          source_document_id?: string | null
          source_type?: Database["public"]["Enums"]["role_source_type"]
          target_role?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "role_profiles_current_analysis_fk"
            columns: ["current_analysis_version_id"]
            isOneToOne: false
            referencedRelation: "role_analysis_versions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "role_profiles_source_document_id_fkey"
            columns: ["source_document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "role_profiles_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      roles: {
        Row: {
          created_at: string
          id: string
          name: string
        }
        Insert: {
          created_at?: string
          id?: string
          name: string
        }
        Update: {
          created_at?: string
          id?: string
          name?: string
        }
        Relationships: []
      }
      rubrics: {
        Row: {
          competency_anchors: Json
          created_at: string
          id: string
          must_mention: string[]
          red_flags: string[]
          role_id: string
          round_type: Database["public"]["Enums"]["round_type"]
          rubric_version: string
          skill_id: string
          source: Database["public"]["Enums"]["rubric_source"]
          status: Database["public"]["Enums"]["rubric_status"]
        }
        Insert: {
          competency_anchors: Json
          created_at?: string
          id?: string
          must_mention?: string[]
          red_flags?: string[]
          role_id: string
          round_type: Database["public"]["Enums"]["round_type"]
          rubric_version: string
          skill_id: string
          source: Database["public"]["Enums"]["rubric_source"]
          status?: Database["public"]["Enums"]["rubric_status"]
        }
        Update: {
          competency_anchors?: Json
          created_at?: string
          id?: string
          must_mention?: string[]
          red_flags?: string[]
          role_id?: string
          round_type?: Database["public"]["Enums"]["round_type"]
          rubric_version?: string
          skill_id?: string
          source?: Database["public"]["Enums"]["rubric_source"]
          status?: Database["public"]["Enums"]["rubric_status"]
        }
        Relationships: [
          {
            foreignKeyName: "rubrics_role_id_fkey"
            columns: ["role_id"]
            isOneToOne: false
            referencedRelation: "roles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "rubrics_skill_id_fkey"
            columns: ["skill_id"]
            isOneToOne: false
            referencedRelation: "skills"
            referencedColumns: ["id"]
          },
        ]
      }
      scores: {
        Row: {
          clarity: number | null
          communication: number | null
          composite: number | null
          created_at: string
          depth: number | null
          evidence_quotes: string[]
          evidence_turn_ids: string[]
          id: string
          model_name: string
          model_provider: string
          model_version: string
          prompt_version: string
          question_index: number
          relevance: number | null
          rubric_version: string
          session_id: string
          signal_strength: number
          skill_id: string | null
          status: Database["public"]["Enums"]["score_status"]
        }
        Insert: {
          clarity?: number | null
          communication?: number | null
          composite?: number | null
          created_at?: string
          depth?: number | null
          evidence_quotes?: string[]
          evidence_turn_ids?: string[]
          id?: string
          model_name: string
          model_provider: string
          model_version: string
          prompt_version: string
          question_index: number
          relevance?: number | null
          rubric_version: string
          session_id: string
          signal_strength: number
          skill_id?: string | null
          status: Database["public"]["Enums"]["score_status"]
        }
        Update: {
          clarity?: number | null
          communication?: number | null
          composite?: number | null
          created_at?: string
          depth?: number | null
          evidence_quotes?: string[]
          evidence_turn_ids?: string[]
          id?: string
          model_name?: string
          model_provider?: string
          model_version?: string
          prompt_version?: string
          question_index?: number
          relevance?: number | null
          rubric_version?: string
          session_id?: string
          signal_strength?: number
          skill_id?: string | null
          status?: Database["public"]["Enums"]["score_status"]
        }
        Relationships: [
          {
            foreignKeyName: "scores_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "scores_skill_id_fkey"
            columns: ["skill_id"]
            isOneToOne: false
            referencedRelation: "skills"
            referencedColumns: ["id"]
          },
        ]
      }
      session_document_links: {
        Row: {
          created_at: string
          document_id: string
          session_id: string
        }
        Insert: {
          created_at?: string
          document_id: string
          session_id: string
        }
        Update: {
          created_at?: string
          document_id?: string
          session_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "session_document_links_document_id_fkey"
            columns: ["document_id"]
            isOneToOne: false
            referencedRelation: "documents"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "session_document_links_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      session_events: {
        Row: {
          created_at: string
          event_type: string
          id: string
          payload: Json
          session_id: string
          user_id: string
        }
        Insert: {
          created_at?: string
          event_type: string
          id?: string
          payload?: Json
          session_id: string
          user_id: string
        }
        Update: {
          created_at?: string
          event_type?: string
          id?: string
          payload?: Json
          session_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "session_events_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "session_events_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      session_results: {
        Row: {
          assessment_confidence: number | null
          confidence_note: string
          created_at: string
          interview_readiness_high: number | null
          interview_readiness_internal: number | null
          interview_readiness_low: number | null
          model_name: string
          model_provider: string
          model_version: string
          percentile: number | null
          prescribed_fix: string
          prompt_version: string
          replay_markers: Json
          role_readiness_high: number | null
          role_readiness_internal: number | null
          role_readiness_low: number | null
          root_cause: string
          root_cause_code: string | null
          root_cause_explanation: string | null
          rubric_version: string
          session_id: string
          summary: string | null
          verdict_code: string | null
          verdict_word: string
        }
        Insert: {
          assessment_confidence?: number | null
          confidence_note: string
          created_at?: string
          interview_readiness_high?: number | null
          interview_readiness_internal?: number | null
          interview_readiness_low?: number | null
          model_name: string
          model_provider: string
          model_version: string
          percentile?: number | null
          prescribed_fix: string
          prompt_version: string
          replay_markers?: Json
          role_readiness_high?: number | null
          role_readiness_internal?: number | null
          role_readiness_low?: number | null
          root_cause: string
          root_cause_code?: string | null
          root_cause_explanation?: string | null
          rubric_version: string
          session_id: string
          summary?: string | null
          verdict_code?: string | null
          verdict_word: string
        }
        Update: {
          assessment_confidence?: number | null
          confidence_note?: string
          created_at?: string
          interview_readiness_high?: number | null
          interview_readiness_internal?: number | null
          interview_readiness_low?: number | null
          model_name?: string
          model_provider?: string
          model_version?: string
          percentile?: number | null
          prescribed_fix?: string
          prompt_version?: string
          replay_markers?: Json
          role_readiness_high?: number | null
          role_readiness_internal?: number | null
          role_readiness_low?: number | null
          root_cause?: string
          root_cause_code?: string | null
          root_cause_explanation?: string | null
          rubric_version?: string
          session_id?: string
          summary?: string | null
          verdict_code?: string | null
          verdict_word?: string
        }
        Relationships: [
          {
            foreignKeyName: "session_results_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: true
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      sessions: {
        Row: {
          completed_at: string | null
          completion_pct: number
          created_at: string
          current_primary_question_id: string | null
          current_probe_count: number
          elapsed_seconds: number
          id: string
          jd_text: string
          phase: Database["public"]["Enums"]["interview_phase"]
          phase_started_at: string
          phase_time_budget_seconds: number
          question_plan: Json | null
          recovery_count: number
          resume_url: string | null
          skeptic_mode: Database["public"]["Enums"]["skeptic_mode"]
          started_at: string | null
          status: Database["public"]["Enums"]["session_status"]
          synthetic: boolean
          target_role: string
          total_questions: number
          total_time_budget_seconds: number
          updated_at: string
          user_id: string
        }
        Insert: {
          completed_at?: string | null
          completion_pct?: number
          created_at?: string
          current_primary_question_id?: string | null
          current_probe_count?: number
          elapsed_seconds?: number
          id?: string
          jd_text?: string
          phase?: Database["public"]["Enums"]["interview_phase"]
          phase_started_at?: string
          phase_time_budget_seconds?: number
          question_plan?: Json | null
          recovery_count?: number
          resume_url?: string | null
          skeptic_mode?: Database["public"]["Enums"]["skeptic_mode"]
          started_at?: string | null
          status?: Database["public"]["Enums"]["session_status"]
          synthetic?: boolean
          target_role: string
          total_questions?: number
          total_time_budget_seconds?: number
          updated_at?: string
          user_id: string
        }
        Update: {
          completed_at?: string | null
          completion_pct?: number
          created_at?: string
          current_primary_question_id?: string | null
          current_probe_count?: number
          elapsed_seconds?: number
          id?: string
          jd_text?: string
          phase?: Database["public"]["Enums"]["interview_phase"]
          phase_started_at?: string
          phase_time_budget_seconds?: number
          question_plan?: Json | null
          recovery_count?: number
          resume_url?: string | null
          skeptic_mode?: Database["public"]["Enums"]["skeptic_mode"]
          started_at?: string | null
          status?: Database["public"]["Enums"]["session_status"]
          synthetic?: boolean
          target_role?: string
          total_questions?: number
          total_time_budget_seconds?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "sessions_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      skeptic_analyses: {
        Row: {
          claim_update_proposals_created: number
          completed_at: string | null
          created_at: string
          failure_type: string | null
          flags_created: number
          id: string
          latency_ms: number
          model: string
          new_claims_created: number
          observations_created: number
          prompt_version: string
          retry_count: number
          session_id: string
          shadow_mode: boolean
          skeptic_execution_id: string
          source_turn_id: string
          structured_output: Json | null
          success: boolean
          user_id: string
        }
        Insert: {
          claim_update_proposals_created?: number
          completed_at?: string | null
          created_at?: string
          failure_type?: string | null
          flags_created?: number
          id?: string
          latency_ms: number
          model: string
          new_claims_created?: number
          observations_created?: number
          prompt_version: string
          retry_count: number
          session_id: string
          shadow_mode: boolean
          skeptic_execution_id: string
          source_turn_id: string
          structured_output?: Json | null
          success: boolean
          user_id: string
        }
        Update: {
          claim_update_proposals_created?: number
          completed_at?: string | null
          created_at?: string
          failure_type?: string | null
          flags_created?: number
          id?: string
          latency_ms?: number
          model?: string
          new_claims_created?: number
          observations_created?: number
          prompt_version?: string
          retry_count?: number
          session_id?: string
          shadow_mode?: boolean
          skeptic_execution_id?: string
          source_turn_id?: string
          structured_output?: Json | null
          success?: boolean
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "skeptic_analyses_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_analyses_source_turn_id_fkey"
            columns: ["source_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_analyses_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      skeptic_claim_update_proposals: {
        Row: {
          accepted: boolean | null
          claim_id: string
          confidence: number
          created_at: string
          dedupe_key: string
          id: string
          proposed_status: Database["public"]["Enums"]["claim_status"]
          reason: string
          related_turn_ids: string[]
          reviewed: boolean
          reviewed_at: string | null
          reviewed_by: string | null
          session_id: string
          skeptic_execution_id: string
          source_turn_id: string
          user_id: string
        }
        Insert: {
          accepted?: boolean | null
          claim_id: string
          confidence: number
          created_at?: string
          dedupe_key: string
          id?: string
          proposed_status: Database["public"]["Enums"]["claim_status"]
          reason: string
          related_turn_ids?: string[]
          reviewed?: boolean
          reviewed_at?: string | null
          reviewed_by?: string | null
          session_id: string
          skeptic_execution_id: string
          source_turn_id: string
          user_id: string
        }
        Update: {
          accepted?: boolean | null
          claim_id?: string
          confidence?: number
          created_at?: string
          dedupe_key?: string
          id?: string
          proposed_status?: Database["public"]["Enums"]["claim_status"]
          reason?: string
          related_turn_ids?: string[]
          reviewed?: boolean
          reviewed_at?: string | null
          reviewed_by?: string | null
          session_id?: string
          skeptic_execution_id?: string
          source_turn_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "skeptic_claim_update_proposals_claim_id_fkey"
            columns: ["claim_id"]
            isOneToOne: false
            referencedRelation: "claims"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_claim_update_proposals_reviewed_by_fkey"
            columns: ["reviewed_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_claim_update_proposals_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_claim_update_proposals_source_turn_id_fkey"
            columns: ["source_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_claim_update_proposals_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      skeptic_observations: {
        Row: {
          confidence: number
          created_at: string
          dedupe_key: string
          id: string
          observation_type: string
          related_claim_ids: string[]
          related_turn_ids: string[]
          session_id: string
          skeptic_execution_id: string
          source_turn_id: string
          summary: string
          user_id: string
        }
        Insert: {
          confidence: number
          created_at?: string
          dedupe_key: string
          id?: string
          observation_type: string
          related_claim_ids?: string[]
          related_turn_ids?: string[]
          session_id: string
          skeptic_execution_id: string
          source_turn_id: string
          summary: string
          user_id: string
        }
        Update: {
          confidence?: number
          created_at?: string
          dedupe_key?: string
          id?: string
          observation_type?: string
          related_claim_ids?: string[]
          related_turn_ids?: string[]
          session_id?: string
          skeptic_execution_id?: string
          source_turn_id?: string
          summary?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "skeptic_observations_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_observations_source_turn_id_fkey"
            columns: ["source_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "skeptic_observations_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      skills: {
        Row: {
          created_at: string
          id: string
          name: string
        }
        Insert: {
          created_at?: string
          id?: string
          name: string
        }
        Update: {
          created_at?: string
          id?: string
          name?: string
        }
        Relationships: []
      }
      specialist_assessments: {
        Row: {
          assessor_type: Database["public"]["Enums"]["specialist_assessor_type"]
          created_at: string
          id: string
          model: string
          model_version: string
          prompt_version: string
          result_json: Json
          rubric_version: string
          session_id: string
          status: Database["public"]["Enums"]["specialist_assessment_status"]
        }
        Insert: {
          assessor_type: Database["public"]["Enums"]["specialist_assessor_type"]
          created_at?: string
          id?: string
          model: string
          model_version: string
          prompt_version: string
          result_json: Json
          rubric_version: string
          session_id: string
          status: Database["public"]["Enums"]["specialist_assessment_status"]
        }
        Update: {
          assessor_type?: Database["public"]["Enums"]["specialist_assessor_type"]
          created_at?: string
          id?: string
          model?: string
          model_version?: string
          prompt_version?: string
          result_json?: Json
          rubric_version?: string
          session_id?: string
          status?: Database["public"]["Enums"]["specialist_assessment_status"]
        }
        Relationships: [
          {
            foreignKeyName: "specialist_assessments_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      tts_audio_cache: {
        Row: {
          cache_key: string
          created_at: string
          language: string
          last_used_at: string
          mime_type: string
          model: string
          normalized_text_hash: string
          provider: string
          session_id: string
          storage_path: string
          user_id: string
          voice: string
        }
        Insert: {
          cache_key: string
          created_at?: string
          language: string
          last_used_at?: string
          mime_type: string
          model: string
          normalized_text_hash: string
          provider: string
          session_id: string
          storage_path: string
          user_id: string
          voice: string
        }
        Update: {
          cache_key?: string
          created_at?: string
          language?: string
          last_used_at?: string
          mime_type?: string
          model?: string
          normalized_text_hash?: string
          provider?: string
          session_id?: string
          storage_path?: string
          user_id?: string
          voice?: string
        }
        Relationships: [
          {
            foreignKeyName: "tts_audio_cache_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "tts_audio_cache_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      turns: {
        Row: {
          agent_execution_id: string | null
          audio_mime_type: string | null
          audio_status: string | null
          audio_storage_path: string | null
          audio_url: string | null
          client_turn_id: string | null
          created_at: string
          duration_ms: number | null
          id: string
          latency_ms: number | null
          model: string | null
          parent_question_id: string | null
          phase: Database["public"]["Enums"]["interview_phase"]
          primary_thread_id: string | null
          prompt_version: string | null
          response_to_turn_id: string | null
          retry_count: number | null
          session_id: string
          silence_before_ms: number | null
          speaker: Database["public"]["Enums"]["turn_speaker"]
          stt_confidence: number | null
          stt_detected_language: string | null
          stt_latency_ms: number | null
          stt_metadata: Json
          stt_model: string | null
          stt_provider: string | null
          target_claim_ids: string[]
          target_competency_ids: string[]
          text: string
          tts_language: string | null
          tts_latency_ms: number | null
          tts_metadata: Json
          tts_model: string | null
          tts_provider: string | null
          tts_voice: string | null
          turn_index: number
          turn_type: Database["public"]["Enums"]["turn_type"]
        }
        Insert: {
          agent_execution_id?: string | null
          audio_mime_type?: string | null
          audio_status?: string | null
          audio_storage_path?: string | null
          audio_url?: string | null
          client_turn_id?: string | null
          created_at?: string
          duration_ms?: number | null
          id?: string
          latency_ms?: number | null
          model?: string | null
          parent_question_id?: string | null
          phase: Database["public"]["Enums"]["interview_phase"]
          primary_thread_id?: string | null
          prompt_version?: string | null
          response_to_turn_id?: string | null
          retry_count?: number | null
          session_id: string
          silence_before_ms?: number | null
          speaker: Database["public"]["Enums"]["turn_speaker"]
          stt_confidence?: number | null
          stt_detected_language?: string | null
          stt_latency_ms?: number | null
          stt_metadata?: Json
          stt_model?: string | null
          stt_provider?: string | null
          target_claim_ids?: string[]
          target_competency_ids?: string[]
          text: string
          tts_language?: string | null
          tts_latency_ms?: number | null
          tts_metadata?: Json
          tts_model?: string | null
          tts_provider?: string | null
          tts_voice?: string | null
          turn_index: number
          turn_type: Database["public"]["Enums"]["turn_type"]
        }
        Update: {
          agent_execution_id?: string | null
          audio_mime_type?: string | null
          audio_status?: string | null
          audio_storage_path?: string | null
          audio_url?: string | null
          client_turn_id?: string | null
          created_at?: string
          duration_ms?: number | null
          id?: string
          latency_ms?: number | null
          model?: string | null
          parent_question_id?: string | null
          phase?: Database["public"]["Enums"]["interview_phase"]
          primary_thread_id?: string | null
          prompt_version?: string | null
          response_to_turn_id?: string | null
          retry_count?: number | null
          session_id?: string
          silence_before_ms?: number | null
          speaker?: Database["public"]["Enums"]["turn_speaker"]
          stt_confidence?: number | null
          stt_detected_language?: string | null
          stt_latency_ms?: number | null
          stt_metadata?: Json
          stt_model?: string | null
          stt_provider?: string | null
          target_claim_ids?: string[]
          target_competency_ids?: string[]
          text?: string
          tts_language?: string | null
          tts_latency_ms?: number | null
          tts_metadata?: Json
          tts_model?: string | null
          tts_provider?: string | null
          tts_voice?: string | null
          turn_index?: number
          turn_type?: Database["public"]["Enums"]["turn_type"]
        }
        Relationships: [
          {
            foreignKeyName: "turns_parent_question_id_fkey"
            columns: ["parent_question_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "turns_response_to_turn_id_fkey"
            columns: ["response_to_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "turns_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      voice_turn_metrics: {
        Row: {
          audio_processing_ms: number
          audio_upload_ms: number
          candidate_turn_id: string | null
          context_build_ms: number
          created_at: string
          id: string
          interviewer_ms: number
          interviewer_turn_id: string | null
          session_id: string
          storage_ms: number
          stt_model: string | null
          stt_ms: number
          stt_provider: string | null
          total_turn_ms: number
          tts_model: string | null
          tts_ms: number
          tts_provider: string | null
          turn_index: number | null
          user_id: string
        }
        Insert: {
          audio_processing_ms?: number
          audio_upload_ms?: number
          candidate_turn_id?: string | null
          context_build_ms?: number
          created_at?: string
          id?: string
          interviewer_ms?: number
          interviewer_turn_id?: string | null
          session_id: string
          storage_ms?: number
          stt_model?: string | null
          stt_ms?: number
          stt_provider?: string | null
          total_turn_ms?: number
          tts_model?: string | null
          tts_ms?: number
          tts_provider?: string | null
          turn_index?: number | null
          user_id: string
        }
        Update: {
          audio_processing_ms?: number
          audio_upload_ms?: number
          candidate_turn_id?: string | null
          context_build_ms?: number
          created_at?: string
          id?: string
          interviewer_ms?: number
          interviewer_turn_id?: string | null
          session_id?: string
          storage_ms?: number
          stt_model?: string | null
          stt_ms?: number
          stt_provider?: string | null
          total_turn_ms?: number
          tts_model?: string | null
          tts_ms?: number
          tts_provider?: string | null
          turn_index?: number | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "voice_turn_metrics_candidate_turn_id_fkey"
            columns: ["candidate_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "voice_turn_metrics_interviewer_turn_id_fkey"
            columns: ["interviewer_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "voice_turn_metrics_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "voice_turn_metrics_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      voice_turn_requests: {
        Row: {
          candidate_audio_mime_type: string | null
          candidate_audio_path: string | null
          candidate_turn_id: string | null
          client_turn_id: string
          created_at: string
          error_code: string | null
          id: string
          interviewer_turn_id: string | null
          recorded_duration_ms: number | null
          response_json: Json | null
          session_id: string
          status: string
          updated_at: string
          user_id: string
        }
        Insert: {
          candidate_audio_mime_type?: string | null
          candidate_audio_path?: string | null
          candidate_turn_id?: string | null
          client_turn_id: string
          created_at?: string
          error_code?: string | null
          id?: string
          interviewer_turn_id?: string | null
          recorded_duration_ms?: number | null
          response_json?: Json | null
          session_id: string
          status: string
          updated_at?: string
          user_id: string
        }
        Update: {
          candidate_audio_mime_type?: string | null
          candidate_audio_path?: string | null
          candidate_turn_id?: string | null
          client_turn_id?: string
          created_at?: string
          error_code?: string | null
          id?: string
          interviewer_turn_id?: string | null
          recorded_duration_ms?: number | null
          response_json?: Json | null
          session_id?: string
          status?: string
          updated_at?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "voice_turn_requests_candidate_turn_id_fkey"
            columns: ["candidate_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "voice_turn_requests_interviewer_turn_id_fkey"
            columns: ["interviewer_turn_id"]
            isOneToOne: false
            referencedRelation: "turns"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "voice_turn_requests_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "sessions"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "voice_turn_requests_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      append_claim_version: {
        Args: {
          p_changed_by: Database["public"]["Enums"]["claim_changed_by"]
          p_claim_id: string
          p_new_state: Json
          p_previous_state: Json
          p_reason: string
          p_user_id: string
        }
        Returns: {
          changed_by: Database["public"]["Enums"]["claim_changed_by"]
          claim_id: string
          created_at: string
          id: string
          new_state: Json
          previous_state: Json | null
          reason: string
          user_id: string
          version: number
        }[]
        SetofOptions: {
          from: "*"
          to: "claim_versions"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      apply_interview_state_change: {
        Args: {
          p_event_payload: Json
          p_event_type: string
          p_expected_updated_at: string
          p_session_id: string
          p_user_id: string
          p_values: Json
        }
        Returns: {
          completed_at: string | null
          completion_pct: number
          created_at: string
          current_primary_question_id: string | null
          current_probe_count: number
          elapsed_seconds: number
          id: string
          jd_text: string
          phase: Database["public"]["Enums"]["interview_phase"]
          phase_started_at: string
          phase_time_budget_seconds: number
          question_plan: Json | null
          recovery_count: number
          resume_url: string | null
          skeptic_mode: Database["public"]["Enums"]["skeptic_mode"]
          started_at: string | null
          status: Database["public"]["Enums"]["session_status"]
          synthetic: boolean
          target_role: string
          total_questions: number
          total_time_budget_seconds: number
          updated_at: string
          user_id: string
        }[]
        SetofOptions: {
          from: "*"
          to: "sessions"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      begin_interview_plan: {
        Args: {
          p_planner_model: string
          p_planning_version: string
          p_prompt_version: string
          p_session_id: string
          p_user_id: string
        }
        Returns: {
          active: boolean
          completed_at: string | null
          created_at: string
          error_type: string | null
          execution_id: string | null
          id: string
          plan_json: Json | null
          planner_model: string
          planning_version: string
          prompt_version: string
          session_id: string
          status: Database["public"]["Enums"]["interview_plan_status"]
          user_id: string
          version: number
        }[]
        SetofOptions: {
          from: "*"
          to: "interview_plans"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      build_claim_graph_for_resume_analysis: {
        Args: { p_analysis_id: string; p_user_id: string }
        Returns: undefined
      }
      claim_graph_node_belongs_to_user: {
        Args: {
          p_node_id: string
          p_node_type: Database["public"]["Enums"]["claim_graph_node_type"]
          p_user_id: string
        }
        Returns: boolean
      }
      claim_post_session_assessment: {
        Args: { p_max_attempts: number; p_worker_id: string }
        Returns: {
          attempts: number
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          error: string | null
          id: string
          job_type: string
          locked_at: string | null
          locked_by: string | null
          payload: Json
          run_after: string
          status: Database["public"]["Enums"]["job_status"]
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      claim_skeptic_turn_analysis: {
        Args: { p_max_attempts: number; p_worker_id: string }
        Returns: {
          attempts: number
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          error: string | null
          id: string
          job_type: string
          locked_at: string | null
          locked_by: string | null
          payload: Json
          run_after: string
          status: Database["public"]["Enums"]["job_status"]
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      claim_voice_turn_request: {
        Args: {
          p_client_turn_id: string
          p_recorded_duration_ms: number
          p_session_id: string
          p_user_id: string
        }
        Returns: {
          candidate_audio_mime_type: string
          candidate_audio_path: string
          candidate_turn_id: string
          claimed: boolean
          client_turn_id: string
          created_at: string
          error_code: string
          id: string
          interviewer_turn_id: string
          recorded_duration_ms: number
          response_json: Json
          session_id: string
          status: string
          updated_at: string
          user_id: string
        }[]
      }
      complete_interview_plan: {
        Args: {
          p_execution_id: string
          p_plan: Json
          p_plan_id: string
          p_user_id: string
        }
        Returns: {
          active: boolean
          completed_at: string | null
          created_at: string
          error_type: string | null
          execution_id: string | null
          id: string
          plan_json: Json | null
          planner_model: string
          planning_version: string
          prompt_version: string
          session_id: string
          status: Database["public"]["Enums"]["interview_plan_status"]
          user_id: string
          version: number
        }[]
        SetofOptions: {
          from: "*"
          to: "interview_plans"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      complete_resume_analysis: {
        Args: {
          p_analysis_id: string
          p_execution_id: string
          p_output: Json
          p_user_id: string
        }
        Returns: {
          analysis_version: string
          completed_at: string | null
          created_at: string
          document_id: string
          error_type: string | null
          execution_id: string | null
          id: string
          model: string
          output: Json | null
          prompt_version: string
          status: Database["public"]["Enums"]["resume_analysis_status"]
          user_id: string
          version: number
        }[]
        SetofOptions: {
          from: "*"
          to: "resume_analyses"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      complete_role_analysis: {
        Args: {
          p_analysis_id: string
          p_execution_id: string
          p_output: Json
          p_user_id: string
        }
        Returns: {
          analysis_version: string
          completed_at: string | null
          created_at: string
          error_type: string | null
          execution_id: string | null
          id: string
          model: string
          output: Json | null
          prompt_version: string
          role_profile_id: string
          source_document_id: string | null
          source_type: Database["public"]["Enums"]["role_source_type"]
          status: Database["public"]["Enums"]["role_analysis_status"]
          user_id: string
          version: number
        }[]
        SetofOptions: {
          from: "*"
          to: "role_analysis_versions"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      consume_skeptic_flag: {
        Args: {
          p_allow_shadow?: boolean
          p_current_candidate_turn_index: number
          p_flag_id: string
          p_interviewer_turn_id: string
          p_min_confidence: number
          p_session_id: string
          p_user_id: string
        }
        Returns: boolean
      }
      create_candidate_text_turn: {
        Args: {
          p_client_turn_id: string
          p_phase: Database["public"]["Enums"]["interview_phase"]
          p_primary_thread_id: string
          p_session_id: string
          p_text: string
          p_turn_type: Database["public"]["Enums"]["turn_type"]
          p_user_id: string
        }
        Returns: {
          agent_execution_id: string | null
          audio_mime_type: string | null
          audio_status: string | null
          audio_storage_path: string | null
          audio_url: string | null
          client_turn_id: string | null
          created_at: string
          duration_ms: number | null
          id: string
          latency_ms: number | null
          model: string | null
          parent_question_id: string | null
          phase: Database["public"]["Enums"]["interview_phase"]
          primary_thread_id: string | null
          prompt_version: string | null
          response_to_turn_id: string | null
          retry_count: number | null
          session_id: string
          silence_before_ms: number | null
          speaker: Database["public"]["Enums"]["turn_speaker"]
          stt_confidence: number | null
          stt_detected_language: string | null
          stt_latency_ms: number | null
          stt_metadata: Json
          stt_model: string | null
          stt_provider: string | null
          target_claim_ids: string[]
          target_competency_ids: string[]
          text: string
          tts_language: string | null
          tts_latency_ms: number | null
          tts_metadata: Json
          tts_model: string | null
          tts_provider: string | null
          tts_voice: string | null
          turn_index: number
          turn_type: Database["public"]["Enums"]["turn_type"]
        }[]
        SetofOptions: {
          from: "*"
          to: "turns"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      create_claim_with_version: {
        Args: {
          p_changed_by: Database["public"]["Enums"]["claim_changed_by"]
          p_claim: Json
          p_reason: string
          p_user_id: string
        }
        Returns: {
          claim_text: string
          claim_type: Database["public"]["Enums"]["claim_type"]
          confidence: number
          contradicted_by_turn_id: string | null
          created_at: string
          id: string
          metric_unit: string | null
          metric_value: number | null
          outcome: string | null
          ownership_language: string | null
          project_name: string | null
          resume_analysis_id: string | null
          session_id: string | null
          skill: string | null
          source: Database["public"]["Enums"]["claim_source"]
          source_document_id: string | null
          source_ref: string | null
          source_reference: string | null
          status: Database["public"]["Enums"]["claim_status"]
          synthetic: boolean
          tool: string | null
          updated_at: string
          user_id: string
          verification_priority: Database["public"]["Enums"]["verification_priority"]
        }[]
        SetofOptions: {
          from: "*"
          to: "claims"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      create_interviewer_text_turn: {
        Args: {
          p_agent_execution_id: string
          p_latency_ms: number
          p_model: string
          p_phase: Database["public"]["Enums"]["interview_phase"]
          p_primary_thread_id: string
          p_prompt_version: string
          p_response_to_turn_id: string
          p_retry_count: number
          p_session_id: string
          p_target_claim_ids: string[]
          p_target_competency_ids: string[]
          p_text: string
          p_turn_type: Database["public"]["Enums"]["turn_type"]
          p_user_id: string
        }
        Returns: {
          agent_execution_id: string | null
          audio_mime_type: string | null
          audio_status: string | null
          audio_storage_path: string | null
          audio_url: string | null
          client_turn_id: string | null
          created_at: string
          duration_ms: number | null
          id: string
          latency_ms: number | null
          model: string | null
          parent_question_id: string | null
          phase: Database["public"]["Enums"]["interview_phase"]
          primary_thread_id: string | null
          prompt_version: string | null
          response_to_turn_id: string | null
          retry_count: number | null
          session_id: string
          silence_before_ms: number | null
          speaker: Database["public"]["Enums"]["turn_speaker"]
          stt_confidence: number | null
          stt_detected_language: string | null
          stt_latency_ms: number | null
          stt_metadata: Json
          stt_model: string | null
          stt_provider: string | null
          target_claim_ids: string[]
          target_competency_ids: string[]
          text: string
          tts_language: string | null
          tts_latency_ms: number | null
          tts_metadata: Json
          tts_model: string | null
          tts_provider: string | null
          tts_voice: string | null
          turn_index: number
          turn_type: Database["public"]["Enums"]["turn_type"]
        }[]
        SetofOptions: {
          from: "*"
          to: "turns"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      create_resume_claim_correction: {
        Args: {
          p_claim_id: string
          p_corrected_claim_text: string
          p_document_id: string
          p_review_status: Database["public"]["Enums"]["claim_review_status"]
          p_user_id: string
        }
        Returns: {
          claim_id: string
          corrected_claim_text: string | null
          created_at: string
          id: string
          resume_analysis_id: string
          review_status: Database["public"]["Enums"]["claim_review_status"]
          user_id: string
          version: number
        }[]
        SetofOptions: {
          from: "*"
          to: "resume_claim_corrections"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_post_session_assessment: {
        Args: { p_session_id: string; p_user_id: string }
        Returns: {
          attempts: number
          completed_at: string | null
          created_at: string
          dedupe_key: string | null
          error: string | null
          id: string
          job_type: string
          locked_at: string | null
          locked_by: string | null
          payload: Json
          run_after: string
          status: Database["public"]["Enums"]["job_status"]
          updated_at: string
        }[]
        SetofOptions: {
          from: "*"
          to: "jobs"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      enqueue_skeptic_turn_analysis: {
        Args: {
          p_prompt_version: string
          p_session_id: string
          p_turn_id: string
          p_user_id: string
        }
        Returns: string
      }
      evidence_normalize: { Args: { p_text: string }; Returns: string }
      find_related_claims: {
        Args: { p_claim_id: string; p_user_id: string }
        Returns: {
          claim_text: string
          claim_type: Database["public"]["Enums"]["claim_type"]
          confidence: number
          contradicted_by_turn_id: string | null
          created_at: string
          id: string
          metric_unit: string | null
          metric_value: number | null
          outcome: string | null
          ownership_language: string | null
          project_name: string | null
          resume_analysis_id: string | null
          session_id: string | null
          skill: string | null
          source: Database["public"]["Enums"]["claim_source"]
          source_document_id: string | null
          source_ref: string | null
          source_reference: string | null
          status: Database["public"]["Enums"]["claim_status"]
          synthetic: boolean
          tool: string | null
          updated_at: string
          user_id: string
          verification_priority: Database["public"]["Enums"]["verification_priority"]
        }[]
        SetofOptions: {
          from: "*"
          to: "claims"
          isOneToOne: false
          isSetofReturn: true
        }
      }
      get_eligible_skeptic_flags: {
        Args: {
          p_allow_shadow?: boolean
          p_current_candidate_turn_index: number
          p_min_confidence: number
          p_session_id: string
          p_user_id: string
        }
        Returns: {
          claim_id: string
          claim_summary: string
          claim_verification_priority: string
          confidence: number
          consumed: boolean
          created_at: string
          detected_at_turn: number
          disputed: boolean
          flag_type: string
          id: string
          reason: string
          resolved_at: string
          safe_to_surface: boolean
          severity: string
          shadow_mode: boolean
          suggested_probe: string
        }[]
      }
      insert_validated_claim_evidence: {
        Args: {
          p_claim_id: string
          p_direction: string
          p_document_id: string
          p_execution_id: string
          p_model: string
          p_prompt_version: string
          p_quote_text: string
          p_reason_code: string
          p_source_id: string
          p_source_type: string
          p_strength: string
          p_turn_id: string
          p_user_id: string
        }
        Returns: boolean
      }
      resolve_claim_state: {
        Args: {
          p_claim_id: string
          p_confidence: number
          p_evidence_ids: string[]
          p_expected_status: Database["public"]["Enums"]["claim_status"]
          p_new_status: Database["public"]["Enums"]["claim_status"]
          p_reason: string
          p_trigger_type: Database["public"]["Enums"]["claim_resolution_trigger"]
          p_user_id: string
        }
        Returns: Json
      }
      update_claim_status: {
        Args: {
          p_changed_by: Database["public"]["Enums"]["claim_changed_by"]
          p_claim_id: string
          p_new_status: Database["public"]["Enums"]["claim_status"]
          p_reason: string
          p_user_id: string
        }
        Returns: {
          claim_text: string
          claim_type: Database["public"]["Enums"]["claim_type"]
          confidence: number
          contradicted_by_turn_id: string | null
          created_at: string
          id: string
          metric_unit: string | null
          metric_value: number | null
          outcome: string | null
          ownership_language: string | null
          project_name: string | null
          resume_analysis_id: string | null
          session_id: string | null
          skill: string | null
          source: Database["public"]["Enums"]["claim_source"]
          source_document_id: string | null
          source_ref: string | null
          source_reference: string | null
          status: Database["public"]["Enums"]["claim_status"]
          synthetic: boolean
          tool: string | null
          updated_at: string
          user_id: string
          verification_priority: Database["public"]["Enums"]["verification_priority"]
        }[]
        SetofOptions: {
          from: "*"
          to: "claims"
          isOneToOne: false
          isSetofReturn: true
        }
      }
    }
    Enums: {
      career_intent:
        | "CAMPUS_PLACEMENT"
        | "INTERNSHIP"
        | "FIRST_JOB"
        | "JOB_SWITCH"
        | "SPECIFIC_COMPANY"
        | "EXPLORING"
      career_stage:
        | "STUDENT"
        | "FINAL_YEAR_STUDENT"
        | "FRESHER"
        | "EARLY_CAREER"
        | "EXPERIENCED"
      claim_changed_by: "SYSTEM" | "AI" | "USER" | "ADMIN"
      claim_entity_type:
        | "SKILL"
        | "PROJECT"
        | "TOOL"
        | "COMPANY"
        | "METRIC"
        | "OUTCOME"
        | "RESPONSIBILITY"
      claim_evidence_type:
        | "DOCUMENT_EXCERPT"
        | "INTERVIEW_TURN"
        | "USER_CORRECTION"
        | "SYSTEM_OBSERVATION"
      claim_graph_node_type: "CLAIM" | "ENTITY"
      claim_relation_source:
        | "RESUME_ANALYSIS"
        | "APPLICATION"
        | "USER"
        | "INTERVIEW"
      claim_relation_type:
        | "ABOUT_SKILL"
        | "ABOUT_PROJECT"
        | "USES_TOOL"
        | "ABOUT_COMPANY"
        | "HAS_METRIC"
        | "CLAIMS_OUTCOME"
        | "CLAIMS_OWNERSHIP"
        | "CLAIMS_RESPONSIBILITY"
        | "RELATED_TO"
      claim_resolution_trigger:
        | "SKEPTIC_FLAG"
        | "EVIDENCE_AGENT"
        | "USER_CORRECTION"
        | "ADMIN_REVIEW"
        | "SESSION_FINALIZATION"
      claim_review_status: "CORRECT" | "NEEDS_CORRECTION"
      claim_source: "resume" | "jd" | "spoken" | "project"
      claim_status:
        | "unverified"
        | "corroborated"
        | "contradicted"
        | "walked_back"
        | "partially_held"
        | "insufficient_evidence"
      claim_type:
        | "skill"
        | "project"
        | "scale"
        | "ownership"
        | "tool"
        | "outcome"
        | "experience"
        | "responsibility"
      competency_category:
        | "TECHNICAL"
        | "ANALYTICAL"
        | "DOMAIN"
        | "BEHAVIOURAL"
        | "COMMUNICATION"
        | "TOOL"
      competency_source_type:
        | "JOB_DESCRIPTION_EXPLICIT"
        | "JOB_DESCRIPTION_INFERRED"
        | "SYNTHETIC_CANONICAL"
      document_status: "UPLOADED" | "PROCESSING" | "PROCESSED" | "FAILED"
      document_type: "RESUME" | "JOB_DESCRIPTION" | "PROJECT"
      evidence_category:
        | "RESUME"
        | "PROJECT"
        | "CASE_STUDY"
        | "CERTIFICATE"
        | "PORTFOLIO"
        | "COVER_LETTER"
        | "ACHIEVEMENT"
        | "WORK_SAMPLE"
        | "ROLE_BRIEF"
        | "OTHER"
      evidence_direction: "SUPPORTS" | "WEAKENS" | "CONTEXT_ONLY"
      expected_competency_level:
        | "FOUNDATIONAL"
        | "BASIC"
        | "INTERMEDIATE"
        | "ADVANCED"
      flag_type:
        | "contradiction"
        | "vagueness"
        | "unsupported_scale"
        | "ownership_drift"
        | "clarification"
        | "additional_detail"
        | "scope_difference"
        | "timeline_difference"
        | "paraphrase"
        | "corroboration"
      interview_phase:
        | "INTRO"
        | "BACKGROUND"
        | "PROJECTS"
        | "ROLE_CORE"
        | "DEEP_DIVE"
        | "BEHAVIOURAL"
        | "CLOSING"
        | "COMPLETE"
      interview_plan_status: "PROCESSING" | "COMPLETED" | "FAILED"
      interview_timeline:
        | "TODAY"
        | "THIS_WEEK"
        | "THIS_MONTH"
        | "LATER"
        | "EXPLORING"
      inquiry_depth:
        | "EVIDENCE_BEHIND_CLAIMS"
        | "ROLE_KNOWLEDGE"
        | "DECISION_QUALITY"
        | "OWNERSHIP_IMPACT"
        | "COMMUNICATION_UNDER_SCRUTINY"
        | "COMPLETE_READINESS"
      job_status: "pending" | "running" | "complete" | "failed"
      preferred_language: "ENGLISH" | "HINDI" | "KANNADA" | "TAMIL" | "TELUGU"
      resume_analysis_status: "PROCESSING" | "COMPLETED" | "FAILED"
      role_analysis_status: "PROCESSING" | "COMPLETED" | "FAILED"
      role_seniority:
        | "ENTRY_LEVEL"
        | "JUNIOR"
        | "MID_LEVEL"
        | "SENIOR"
        | "LEAD"
        | "UNSPECIFIED"
      role_source_type: "JOB_DESCRIPTION" | "SYNTHETIC_CANONICAL"
      round_type: "screening" | "technical" | "managerial" | "hr"
      rubric_source: "synthetic-draft" | "expert" | "validated"
      rubric_status: "draft" | "active" | "contested"
      score_status: "scored" | "not_enough_signal"
      session_status:
        | "draft"
        | "prepared"
        | "in_progress"
        | "processing"
        | "complete"
        | "failed"
        | "CREATED"
        | "PREPARING"
        | "READY"
        | "ACTIVE"
        | "ASSESSING"
        | "COMPLETED"
        | "FAILED"
      skeptic_mode: "shadow" | "active"
      specialist_assessment_status: "COMPLETE" | "NOT_ENOUGH_SIGNAL"
      specialist_assessor_type: "TECHNICAL" | "BEHAVIOUR" | "CLAIMS"
      turn_speaker: "candidate" | "interviewer"
      turn_type:
        | "planned"
        | "depth_probe"
        | "contradiction_probe"
        | "ladder_up"
        | "ladder_down"
        | "recovery"
        | "transition"
        | "closing"
      verification_priority: "LOW" | "MEDIUM" | "HIGH"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      career_intent: [
        "CAMPUS_PLACEMENT",
        "INTERNSHIP",
        "FIRST_JOB",
        "JOB_SWITCH",
        "SPECIFIC_COMPANY",
        "EXPLORING",
      ],
      career_stage: [
        "STUDENT",
        "FINAL_YEAR_STUDENT",
        "FRESHER",
        "EARLY_CAREER",
        "EXPERIENCED",
      ],
      claim_changed_by: ["SYSTEM", "AI", "USER", "ADMIN"],
      claim_entity_type: [
        "SKILL",
        "PROJECT",
        "TOOL",
        "COMPANY",
        "METRIC",
        "OUTCOME",
        "RESPONSIBILITY",
      ],
      claim_evidence_type: [
        "DOCUMENT_EXCERPT",
        "INTERVIEW_TURN",
        "USER_CORRECTION",
        "SYSTEM_OBSERVATION",
      ],
      claim_graph_node_type: ["CLAIM", "ENTITY"],
      claim_relation_source: [
        "RESUME_ANALYSIS",
        "APPLICATION",
        "USER",
        "INTERVIEW",
      ],
      claim_relation_type: [
        "ABOUT_SKILL",
        "ABOUT_PROJECT",
        "USES_TOOL",
        "ABOUT_COMPANY",
        "HAS_METRIC",
        "CLAIMS_OUTCOME",
        "CLAIMS_OWNERSHIP",
        "CLAIMS_RESPONSIBILITY",
        "RELATED_TO",
      ],
      claim_resolution_trigger: [
        "SKEPTIC_FLAG",
        "EVIDENCE_AGENT",
        "USER_CORRECTION",
        "ADMIN_REVIEW",
        "SESSION_FINALIZATION",
      ],
      claim_review_status: ["CORRECT", "NEEDS_CORRECTION"],
      claim_source: ["resume", "jd", "spoken", "project"],
      claim_status: [
        "unverified",
        "corroborated",
        "contradicted",
        "walked_back",
        "partially_held",
        "insufficient_evidence",
      ],
      claim_type: [
        "skill",
        "project",
        "scale",
        "ownership",
        "tool",
        "outcome",
        "experience",
        "responsibility",
      ],
      competency_category: [
        "TECHNICAL",
        "ANALYTICAL",
        "DOMAIN",
        "BEHAVIOURAL",
        "COMMUNICATION",
        "TOOL",
      ],
      competency_source_type: [
        "JOB_DESCRIPTION_EXPLICIT",
        "JOB_DESCRIPTION_INFERRED",
        "SYNTHETIC_CANONICAL",
      ],
      document_status: ["UPLOADED", "PROCESSING", "PROCESSED", "FAILED"],
      document_type: ["RESUME", "JOB_DESCRIPTION", "PROJECT"],
      evidence_category: [
        "RESUME",
        "PROJECT",
        "CASE_STUDY",
        "CERTIFICATE",
        "PORTFOLIO",
        "COVER_LETTER",
        "ACHIEVEMENT",
        "WORK_SAMPLE",
        "ROLE_BRIEF",
        "OTHER",
      ],
      evidence_direction: ["SUPPORTS", "WEAKENS", "CONTEXT_ONLY"],
      expected_competency_level: [
        "FOUNDATIONAL",
        "BASIC",
        "INTERMEDIATE",
        "ADVANCED",
      ],
      flag_type: [
        "contradiction",
        "vagueness",
        "unsupported_scale",
        "ownership_drift",
        "clarification",
        "additional_detail",
        "scope_difference",
        "timeline_difference",
        "paraphrase",
        "corroboration",
      ],
      interview_phase: [
        "INTRO",
        "BACKGROUND",
        "PROJECTS",
        "ROLE_CORE",
        "DEEP_DIVE",
        "BEHAVIOURAL",
        "CLOSING",
        "COMPLETE",
      ],
      interview_plan_status: ["PROCESSING", "COMPLETED", "FAILED"],
      interview_timeline: [
        "TODAY",
        "THIS_WEEK",
        "THIS_MONTH",
        "LATER",
        "EXPLORING",
      ],
      inquiry_depth: [
        "EVIDENCE_BEHIND_CLAIMS",
        "ROLE_KNOWLEDGE",
        "DECISION_QUALITY",
        "OWNERSHIP_IMPACT",
        "COMMUNICATION_UNDER_SCRUTINY",
        "COMPLETE_READINESS",
      ],
      job_status: ["pending", "running", "complete", "failed"],
      preferred_language: ["ENGLISH", "HINDI", "KANNADA", "TAMIL", "TELUGU"],
      resume_analysis_status: ["PROCESSING", "COMPLETED", "FAILED"],
      role_analysis_status: ["PROCESSING", "COMPLETED", "FAILED"],
      role_seniority: [
        "ENTRY_LEVEL",
        "JUNIOR",
        "MID_LEVEL",
        "SENIOR",
        "LEAD",
        "UNSPECIFIED",
      ],
      role_source_type: ["JOB_DESCRIPTION", "SYNTHETIC_CANONICAL"],
      round_type: ["screening", "technical", "managerial", "hr"],
      rubric_source: ["synthetic-draft", "expert", "validated"],
      rubric_status: ["draft", "active", "contested"],
      score_status: ["scored", "not_enough_signal"],
      session_status: [
        "draft",
        "prepared",
        "in_progress",
        "processing",
        "complete",
        "failed",
        "CREATED",
        "PREPARING",
        "READY",
        "ACTIVE",
        "ASSESSING",
        "COMPLETED",
        "FAILED",
      ],
      skeptic_mode: ["shadow", "active"],
      specialist_assessment_status: ["COMPLETE", "NOT_ENOUGH_SIGNAL"],
      specialist_assessor_type: ["TECHNICAL", "BEHAVIOUR", "CLAIMS"],
      turn_speaker: ["candidate", "interviewer"],
      turn_type: [
        "planned",
        "depth_probe",
        "contradiction_probe",
        "ladder_up",
        "ladder_down",
        "recovery",
        "transition",
        "closing",
      ],
      verification_priority: ["LOW", "MEDIUM", "HIGH"],
    },
  },
} as const
