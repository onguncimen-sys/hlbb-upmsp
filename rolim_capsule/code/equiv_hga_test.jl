#=
EQUIVALENCE HARNESS (HGA nis-genisletmesi). Sabit-iter -> deterministik.
Ayni seed + sabit instance ile: extended-HGA (pure mod) == original-HGA (RNG birebir).
Kullanim: julia equiv_hga_test.jl <HGA.jl-yolu> <alg_seed>  -> EQUIV_RESULT <best> <checksum>
=#
include(ARGS[1])          # test edilecek HGA.jl (orig ya da extended)
using Random

# ---- SABIT instance (SA harness ile ayni uretim): seed 12345 ----
Random.seed!(12345)
m = Int8(5); n = Int16(40)
p = Int16.(rand(1:99, Int(m), Int(n)))
S = Matrix{Int16}[ Int16.([i == j ? 0 : rand(1:99) for i in 1:Int(n), j in 1:Int(n)]) for _ in 1:Int(m) ]

if isdefined(Main, :_set_niche!)
    _set_niche!(Int(m), Int(n), nothing, nothing)   # pure-mod (orig'de tanimsiz -> atlanir)
end

function run_harness(seed_arg, m, n, p, S)
    Random.seed!(parse(Int, seed_arg))
    P = Int8(15)
    dnn = Float16(0.8); dins = Float16(0.8); dswap = Float16(0.8)
    POP = InitPopulation(m, n, P, p, S)

    best::Int32 = BestOF(POP)
    checksum::Int64 = 0
    for it in 1:500     # HGA LocalSearch = tam VND-inisi (agir); RNG sapmasi ilk iterlerde belli olur
        O1, O2, _ = CrossOver(POP, P, m, p, S)
        LocalSearch(O1, m, p, S, dnn, dins, dswap)
        LocalSearch(O2, m, p, S, dnn, dins, dswap)
        UpdatePopulation(O1, POP)
        UpdatePopulation(O2, POP)
        c::Int32 = BestOF(POP)
        if c < best; best = c; end
        checksum += Int64(c)                  # trajektori parmak-izi
    end
    return best, checksum
end

best, checksum = run_harness(ARGS[2], m, n, p, S)
println("EQUIV_RESULT $best $checksum")
