#=
EQUIVALENCE HARNESS (GA nis-genisletmesi). Sabit-iter -> deterministik.
extended-GA (pure mod) == original-GA (RNG birebir).
Kullanim: julia equiv_ga_test.jl <GA.jl-yolu> <alg_seed>  -> EQUIV_RESULT <best> <checksum>
=#
include(ARGS[1])
using Random

Random.seed!(12345)
m = Int8(5); n = Int16(40)
p = Int16.(rand(1:99, Int(m), Int(n)))
S = Matrix{Int16}[ Int16.([i == j ? 0 : rand(1:99) for i in 1:Int(n), j in 1:Int(n)]) for _ in 1:Int(m) ]

if isdefined(Main, :_set_niche!)
    _set_niche!(Int(m), Int(n), nothing, nothing)   # pure-mod
end

function run_harness(seed_arg, m, n, p, S)
    Random.seed!(parse(Int, seed_arg))
    Psize = Int8(80); Pc = Float16(0.5); Pm = Float16(0.5)
    Pls = Float16(1.0); Pressure = Int8(10)
    POP = Init_Pop(Psize, m, n, p, S)

    best::Int32 = minimum(j -> j.Fit, POP)
    checksum::Int64 = 0
    for it in 1:300
        O1, O2, _ = CrossOver(POP, Pc, Pressure, Psize, m, p, S)
        IMI_LS(Pls, m, p, S, O1)
        IMI_LS(Pls, m, p, S, O2)
        Mutation(O1, O2, Pm, m, p, S)
        UpdatePopulation(O1, POP, Psize)
        UpdatePopulation(O2, POP, Psize)
        c::Int32 = minimum(j -> j.Fit, POP)
        if c < best; best = c; end
        checksum += Int64(c)
    end
    return best, checksum
end

best, checksum = run_harness(ARGS[2], m, n, p, S)
println("EQUIV_RESULT $best $checksum")
