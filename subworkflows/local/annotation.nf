//
// MODULE: Installed directly from nf-core/modules
//
include { PROKKA                } from '../../modules/nf-core/prokka/main'
include { BAKTA } from '../../modules/nf-core/bakta/main'
include { GET_CAZYDB;
          GET_VFDB;
          GET_BACMET} from '../../modules/local/blast_databases.nf'
include { DIAMOND_MAKEDB as DIAMOND_MAKE_CAZY;
          DIAMOND_MAKEDB as DIAMOND_MAKE_VFDB;
          DIAMOND_MAKEDB as DIAMOND_MAKE_BACMET } from '../../modules/nf-core/diamond/makedb/main'
include { DIAMOND_BLASTX as DIAMOND_BLAST_CAZY;
          DIAMOND_BLASTX as DIAMOND_BLAST_VFDB;
          DIAMOND_BLASTX as DIAMOND_BLAST_BACMET } from '../../modules/nf-core/diamond/blastx/main'
//
// MODULE: Local to the pipeline
//
include { GET_SOFTWARE_VERSIONS } from '../../modules/local/get_software_versions'
include { RGI;
          UPDATE_RGI_DB } from '../../modules/local/rgi'
include { MOB_RECON } from '../../modules/local/mobsuite'

workflow ANNOTATE_ASSEMBLIES {
    take:
        assemblies
        bakta_db
        vfdb_cache
        cazydb_cache
        bacmet_cache
        card_json_cache
        card_version_cache


    main:

        //if (params.input_sample_table){ ch_input = file(params.input_sample_table) } else { exit 1, 'Input samplesheet not specified!' }
        ch_software_versions = Channel.empty()
        /*
        * SUBWORKFLOW: Read in samplesheet, validate and stage input files
        */
        //ANNOTATION_INPUT_CHECK(ch_input)

        /*
        * Load in the databases. Check if they were cached, otherwise run the processes that get them
        */

        // Note: I hate how inelegant this block is. Works for now, but consider looking for a more elegant nextflow pattern
        /*
        * Load BLAST databases
        */
        if (vfdb_cache){
            vfdb_cache.set { ch_vfdb }
        }
        else{
            GET_VFDB()
            GET_VFDB.out.vfdb.set { ch_vfdb }
        }
        if(bacmet_cache){
            bacmet_cache.set { ch_bacmet_db }
        }
        else{
            GET_BACMET()
            GET_BACMET.out.bacmet.set { ch_bacmet_db }
        }
        if (cazydb_cache){
            cazydb_cache.set{ ch_cazy_db }
        }
        else{
            GET_CAZYDB()
            GET_CAZYDB.out.cazydb.set { ch_cazy_db }
        }
        /*
        * Load RGI for AMR annotation
        */
        if (card_json_cache){
            card_json_cache.set { ch_card_json }
            ch_software_versions = ch_software_versions.mix(card_version_cache)
        }
        else{
            UPDATE_RGI_DB()
            UPDATE_RGI_DB.out.card_json.set { ch_card_json }
            ch_software_versions = ch_software_versions.mix(UPDATE_RGI_DB.out.card_version.ifEmpty(null))
        }


        /*
        * Run RGI
        */
        RGI(assemblies, ch_card_json)
        ch_software_versions = ch_software_versions.mix(RGI.out.version.first().ifEmpty(null))


        /*
        * Run gene finding software (Prokka or Bakta)
        */
        ch_ffn_files = Channel.empty()
        ch_gff_files = Channel.empty()
        if (bakta_db){
            BAKTA(assemblies, bakta_db, [], [])
            ch_software_versions = ch_software_versions.mix(BAKTA.out.versions.first().ifEmpty(null))
            ch_ffn_files = ch_ffn_files.mix(BAKTA.out.ffn)
            ch_gff_files = ch_gff_files.mix(BAKTA.out.gff)
        }
        else{
            PROKKA (
            assemblies,
            [],
            []
            ) //Assembly, protein file, pre-trained prodigal
            ch_software_versions = ch_software_versions.mix(PROKKA.out.versions.first().ifEmpty(null))
            ch_ffn_files = ch_ffn_files.mix(PROKKA.out.ffn)
            ch_gff_files = ch_gff_files.mix(PROKKA.out.gff)
        }

        /*
        * Module: Mob-Suite. Database is included in singularity container
        */
        MOB_RECON(assemblies)
        ch_software_versions = ch_software_versions.mix(MOB_RECON.out.version.first().ifEmpty(null))



        /*
        * Run DIAMOND blast annotation with databases
        */
        def blast_columns = "qseqid sseqid pident slen qlen length mismatch gapopen qstart qend sstart send evalue bitscore full_qseq"
        DIAMOND_MAKE_CAZY(ch_cazy_db)
        ch_software_versions = ch_software_versions.mix(DIAMOND_MAKE_CAZY.out.versions.ifEmpty(null))
        DIAMOND_BLAST_CAZY(ch_ffn_files, DIAMOND_MAKE_CAZY.out.db, "txt", blast_columns)

        DIAMOND_MAKE_VFDB(ch_vfdb)
        DIAMOND_BLAST_VFDB(ch_ffn_files, DIAMOND_MAKE_VFDB.out.db, "txt", blast_columns)

        DIAMOND_MAKE_BACMET(ch_bacmet_db)
        DIAMOND_BLAST_BACMET(ch_ffn_files, DIAMOND_MAKE_BACMET.out.db, "txt", blast_columns)

        ch_multiqc_files = Channel.empty()
        if(!bakta_db){
            ch_multiqc_files = ch_multiqc_files.mix(PROKKA.out.txt.collect{it[1]}.ifEmpty([]))
        }

    emit:
        annotation_software = ch_software_versions
        multiqc = ch_multiqc_files
        gff = ch_gff_files

}
